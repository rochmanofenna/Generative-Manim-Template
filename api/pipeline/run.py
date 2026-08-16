"""Pipeline orchestrator: generate -> sanitize -> render (with retry) -> done.

Collaborators are injected rather than imported so this module stays free of any
dependency on the Flask routes, which already import from `api.pipeline.llm`.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
import re
import time

from .events import RunRecorder
from .llm import LLMResult
from .sanitize import describe_rewrites, extract_code_from_markdown, sanitize_code
from .validate import MAX_NARRATION_CHARS, validate_scene

VALIDATION_PROMPT = """The Manim scene below failed pre-flight checks:

{problems}

Here is the scene:
```python
{code}
```

Return the complete corrected scene, and nothing else. Keep the same class name.
Every self.voiceover(text=...) block must be one or two short sentences, well
under """ + str(MAX_NARRATION_CHARS) + """ characters -- split long narration
across several blocks, each wrapping its own animation."""

REPAIR_PROMPT = """The Manim scene below failed to render. Fix it.

Here is the error output from Manim:
```
{error}
```

Here is the scene that failed:
```python
{code}
```

Return the complete corrected scene, and nothing else. Keep the same class name.
Common causes: invalid LaTeX in Tex() or MathTex(), a method that does not exist
on the object, or a mobject used before it was created."""

# Manim logs are long; only the tail carries the actual traceback, and sending
# the whole thing wastes input tokens on progress-bar noise.
ERROR_TAIL_CHARS = 4000

# Failures the model cannot fix. gTTS in particular rate-limits under repeated
# renders. Re-rendering the same code after a pause is the right response;
# paying for an LLM round trip to "repair" an outage is not.
TRANSIENT_MARKERS = (
    "gTTS gave an error",
    "not connected to the internet",
    "Connection error",
    "Read timed out",
    "Temporary failure in name resolution",
    "Max retries exceeded",
    "503 Server Error",
    "429 Client Error",
)


def is_transient(log: str) -> bool:
    """True when the failure is infrastructure, not something in the scene."""
    return any(marker in log for marker in TRANSIENT_MARKERS)


@dataclass
class RunResult:
    video_path: str
    code: str
    recorder: RunRecorder
    attempts: int = 1
    llm_calls: List[LLMResult] = field(default_factory=list)
    extra_meta: Dict = field(default_factory=dict)

    @property
    def total_input_tokens(self) -> Optional[int]:
        values = [c.input_tokens for c in self.llm_calls if c.input_tokens is not None]
        return sum(values) if values else None

    @property
    def total_output_tokens(self) -> Optional[int]:
        values = [c.output_tokens for c in self.llm_calls if c.output_tokens is not None]
        return sum(values) if values else None

    @property
    def total_cost_cents(self) -> Optional[float]:
        values = [c.cost_cents for c in self.llm_calls if c.cost_cents is not None]
        return round(sum(values), 4) if values else None

    def to_meta(self) -> Dict:
        run = self.recorder.to_run_json()
        meta = {
            "slug": self.recorder.slug,
            "model": self.llm_calls[0].model if self.llm_calls else None,
            "attempts": self.attempts,
            "llm_calls": len(self.llm_calls),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_cents": self.total_cost_cents,
            "total_ms": run["total_ms"],
        }
        meta.update(self.extra_meta)
        return meta


def run_pipeline(
    prompt: str,
    slug: str,
    *,
    generate: Callable[..., LLMResult],
    render: Callable[..., object],
    workdir: str,
    model: Optional[str] = None,
    domain: str = "default",
    quality: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    voiceover: bool = True,
    max_attempts: int = 3,
    recorder: Optional[RunRecorder] = None,
    backoff_seconds: int = 20,
    sleep: Callable[[float], None] = time.sleep,
):
    """Run the full pipeline, yielding progress dicts.

    Yields the same progress shape the renderer emits, plus a final
    {"result": RunResult}. Raises whatever the renderer raises once attempts are
    exhausted, so the caller still sees the underlying error.
    """
    recorder = recorder or RunRecorder(slug)
    llm_calls: List[LLMResult] = []

    # --- generate ---------------------------------------------------------
    recorder.emit("code_generation", f"generating scene for {slug!r}")
    result = generate(prompt, model, domain, voiceover)
    llm_calls.append(result)
    recorder.emit("code_generation", result.summary())
    yield {"stage": "code_generation", "msg": result.summary()}

    code = extract_code_from_markdown(result.text)

    # --- sanitize ---------------------------------------------------------
    code, counts = sanitize_code(code)
    message = describe_rewrites(counts)
    recorder.emit("sanitize", message, level="warn" if counts else "info")
    yield {"stage": "sanitize", "msg": message}

    # --- validate, repairing before spending a render ---------------------
    for check in range(1, max_attempts + 1):
        problems = validate_scene(code, voiceover)
        if not problems:
            recorder.emit("validate", "scene passed pre-flight checks")
            yield {"stage": "validate", "msg": "passed"}
            break

        for problem in problems:
            recorder.emit("validate", problem, level="warn")
        yield {"stage": "validate", "msg": problems[0], "level": "warn"}

        if check == max_attempts:
            recorder.emit("validate", "proceeding despite unresolved problems",
                          level="warn")
            break

        recorder.emit("validate", f"retry {check}/{max_attempts - 1}: asking model to fix",
                      level="warn")
        fixed = generate(
            VALIDATION_PROMPT.format(problems="\n".join(f"- {p}" for p in problems),
                                     code=code),
            model, domain, voiceover,
        )
        llm_calls.append(fixed)
        recorder.emit("code_generation", f"revision: {fixed.summary()}")
        code, counts = sanitize_code(extract_code_from_markdown(fixed.text))
        if counts:
            recorder.emit("sanitize", describe_rewrites(counts), level="warn")

    # --- render, retrying on failure -------------------------------------
    last_error = None
    for attempt in range(1, max_attempts + 1):
        recorder.emit("render", f"attempt {attempt}/{max_attempts}: starting manim")
        video_path = None
        try:
            for event in render(code, "GenScene", aspect_ratio, workdir, quality, voiceover):
                if "video_path" in event:
                    video_path = event["video_path"]
                else:
                    yield event
        except Exception as e:  # RenderError, kept generic to avoid a hard import
            last_error = e
            log = getattr(e, "log", "") or str(e)
            recorder.emit("render", f"attempt {attempt} failed: {_first_error_line(log)}",
                          level="error")
            yield {"stage": "render", "msg": f"attempt {attempt} failed", "level": "error"}

            if attempt == max_attempts:
                recorder.emit("render", f"giving up after {max_attempts} attempts",
                              level="error")
                raise

            if is_transient(log):
                # Nothing wrong with the scene -- back off and render it again.
                delay = backoff_seconds * attempt
                recorder.emit(
                    "render",
                    f"retry {attempt}/{max_attempts - 1}: transient failure, "
                    f"re-rendering in {delay}s",
                    level="warn",
                )
                sleep(delay)
                continue

            recorder.emit("render", f"retry {attempt}/{max_attempts - 1}: asking model to fix",
                          level="warn")
            repair = generate(
                REPAIR_PROMPT.format(error=log[-ERROR_TAIL_CHARS:], code=code),
                model, domain, voiceover,
            )
            llm_calls.append(repair)
            recorder.emit("code_generation", f"repair: {repair.summary()}")
            code, counts = sanitize_code(extract_code_from_markdown(repair.text))
            if counts:
                recorder.emit("sanitize", describe_rewrites(counts), level="warn")
            continue

        recorder.emit("done", "render complete")
        yield {
            "result": RunResult(
                video_path=video_path,
                code=code,
                recorder=recorder,
                attempts=attempt,
                llm_calls=llm_calls,
            )
        }
        return

    raise last_error  # pragma: no cover - loop always returns or raises


def _first_error_line(log: str) -> str:
    """Pull the most informative single line out of a Manim traceback."""
    for line in reversed(log.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\w*(Error|Exception)\b", line) or ": " in line:
            return line[:200]
    return (log.strip().splitlines() or ["unknown error"])[-1][:200]
