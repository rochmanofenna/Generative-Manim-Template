"""Repair characters an LLM emits that Manim's LaTeX pass cannot compile.

Models routinely produce typographic punctuation -- em dashes, curly quotes,
ellipses -- inside Tex() and MathTex() strings. pdflatex rejects those bytes, so
the render dies with an opaque "Undefined control sequence". Rewriting them to
ASCII before rendering is cheaper than paying for a retry.
"""

from typing import Dict, Tuple
import re


def extract_code_from_markdown(raw_code: str) -> str:
    """Strip a ```python fence if the model wrapped its answer in one.

    Must run before validation: otherwise the validator parses markdown, reports
    a syntax error on line 1, and pays for a repair call to fix nothing.
    """
    match = re.search(r"```(?:python)?\n(.*?)```", raw_code, re.DOTALL)
    code = match.group(1) if match else raw_code
    return code.strip()

# Rewrites are applied to the whole source rather than just string literals:
# these characters have no legitimate use in generated Manim code, and parsing
# out literals would need a full AST round-trip for no practical gain.
REPLACEMENTS: Dict[str, str] = {
    "—": "--",  # em dash
    "–": "-",  # en dash
    "‘": "'",  # left single quote
    "’": "'",  # right single quote
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
    "−": "-",  # minus sign
    "×": r"\times ",  # multiplication sign
    "÷": r"\div ",  # division sign
    "≤": r"\leq ",  # less-than-or-equal
    "≥": r"\geq ",  # greater-than-or-equal
    "≠": r"\neq ",  # not-equal
}

# Human-readable groupings for the run log, so the event says "3 unicode dashes
# rewritten" rather than listing codepoints.
_LABELS: Dict[str, str] = {
    "—": "unicode dashes",
    "–": "unicode dashes",
    "−": "unicode dashes",
    "‘": "smart quotes",
    "’": "smart quotes",
    "“": "smart quotes",
    "”": "smart quotes",
    "…": "ellipses",
    " ": "non-breaking spaces",
    "×": "math symbols",
    "÷": "math symbols",
    "≤": "math symbols",
    "≥": "math symbols",
    "≠": "math symbols",
}


def sanitize_code(code: str) -> Tuple[str, Dict[str, int]]:
    """Return (cleaned code, {label: count}). An empty dict means no rewrites."""
    counts: Dict[str, int] = {}
    for char, replacement in REPLACEMENTS.items():
        occurrences = code.count(char)
        if not occurrences:
            continue
        code = code.replace(char, replacement)
        label = _LABELS[char]
        counts[label] = counts.get(label, 0) + occurrences
    return code, counts


def describe_rewrites(counts: Dict[str, int]) -> str:
    """Render sanitize counts as a log message."""
    if not counts:
        return "no rewrites needed"
    parts = [f"{n} {label}" for label, n in sorted(counts.items())]
    return ", ".join(parts) + " rewritten"
