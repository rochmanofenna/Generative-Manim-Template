"""Provider-agnostic code generation with usage accounting.

Returns an LLMResult rather than a bare string: the run log reports model,
latency, tokens, and cost, and the previous code discarded `response.usage`
entirely.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union
import os
import time

from openai import OpenAI

# Generated Manim scenes routinely run past 1k tokens; too small a cap truncates
# the class mid-definition and the render fails with a SyntaxError.
LLM_MAX_TOKENS = 16000

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"

# USD per million tokens, as (input, output). Models absent here report a null
# cost rather than a guessed one -- a wrong number on a portfolio is worse than
# an absent one. Verify against current pricing before quoting these.
PRICING: Dict[str, Tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
}


class CodeGenerationError(RuntimeError):
    """Raised when the LLM fails to return usable Manim code."""


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    @property
    def cost_cents(self) -> Optional[float]:
        """Cost in cents, or None when the model has no known price."""
        price = PRICING.get(self.model)
        if price is None or self.input_tokens is None or self.output_tokens is None:
            return None
        in_price, out_price = price
        dollars = (self.input_tokens * in_price + self.output_tokens * out_price) / 1e6
        return round(dollars * 100, 4)

    def summary(self) -> str:
        """One-line description for the run log."""
        parts = [f"{self.model} responded in {self.latency_ms / 1000:.1f}s"]
        if self.output_tokens is not None:
            parts.append(f"{self.output_tokens} completion tokens")
        cost = self.cost_cents
        if cost is not None:
            parts.append(f"{cost:.3f}c")
        return ", ".join(parts)


def has_api_key(var_name: str) -> bool:
    """True when the env var holds something that could actually be a key.

    Copying .env.example leaves placeholders like "sk-..." behind; those are
    non-empty, so a bare truthiness check would treat an unconfigured provider
    as configured and route requests to it. Real keys are far longer than this.
    """
    return len((os.getenv(var_name) or "").strip()) >= 20


def resolve_model(requested: Union[str, None] = None) -> str:
    """Pick a model, preferring whichever provider actually has credentials."""
    if requested:
        return requested
    configured = os.getenv("DEFAULT_MODEL")
    if configured:
        return configured
    if has_api_key("ANTHROPIC_API_KEY") and not has_api_key("OPENAI_API_KEY"):
        return DEFAULT_ANTHROPIC_MODEL
    return DEFAULT_OPENAI_MODEL


def _generate_with_anthropic(
    system_prompt: str, prompt_content: str, model: str
) -> LLMResult:
    import anthropic  # imported lazily so the OpenAI path works without it

    # No temperature: it is rejected with a 400 on Claude Opus 5 and the 4.7+
    # family. Steer via the system prompt instead.
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    started = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=LLM_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt_content}],
    )
    latency_ms = round((time.monotonic() - started) * 1000)

    # Check before reading content: a refusal returns HTTP 200 with content
    # empty or partial, so indexing blocks[0] would mislead or crash.
    if response.stop_reason == "refusal":
        raise CodeGenerationError("Claude declined this prompt; try rephrasing it")

    text = "".join(b.text for b in response.content if b.type == "text")
    usage = getattr(response, "usage", None)
    return LLMResult(
        text=text,
        model=model,
        latency_ms=latency_ms,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )


def _generate_with_openai(
    system_prompt: str, prompt_content: str, model: str
) -> LLMResult:
    # Constructed here, not at module import: instantiating OpenAI() raises
    # immediately when OPENAI_API_KEY is unset.
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    started = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_content},
        ],
        temperature=0.2,
    )
    latency_ms = round((time.monotonic() - started) * 1000)

    usage = getattr(response, "usage", None)
    return LLMResult(
        text=response.choices[0].message.content,
        model=model,
        latency_ms=latency_ms,
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
    )


def generate_code(
    system_prompt: str, prompt_content: str, model: Union[str, None] = None
) -> LLMResult:
    """Generate code from a prompt, dispatching on the model name.

    A plain helper, not a view function -- it must never return a Flask response
    tuple, because callers feed the result straight to the renderer.
    """
    model = resolve_model(model)
    try:
        if model.startswith("claude-"):
            result = _generate_with_anthropic(system_prompt, prompt_content, model)
        else:
            result = _generate_with_openai(system_prompt, prompt_content, model)
    except CodeGenerationError:
        raise
    except Exception as e:
        raise CodeGenerationError(f"LLM request failed: {e}") from e
    if not result.text:
        raise CodeGenerationError("LLM returned no code")
    return result
