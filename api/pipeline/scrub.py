"""Redact anything that must not land in a public repo.

Applied to every text artifact before it is written. Two classes of leak matter:
absolute paths that expose a home directory layout, and anything key-shaped.
"""

from typing import Dict
import os
import re

# Order matters: the workdir pattern is more specific than the home directory.
_PATTERNS = [
    (re.compile(r"/tmp/genmanim-[A-Za-z0-9_]+"), "<workdir>"),
    (re.compile(r"/home/[A-Za-z0-9_.-]+"), "~"),
    (re.compile(r"/Users/[A-Za-z0-9_.-]+"), "~"),
    # Provider keys. Deliberately broad: a false positive costs nothing, a miss
    # publishes a credential.
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "<redacted-key>"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "<redacted-key>"),
    (re.compile(r"(?i)\b(api[_-]?key|authorization|bearer)\b\s*[:=]\s*\S+"),
     r"\1=<redacted>"),
]


def scrub_text(text: str) -> str:
    """Return text with paths rewritten and secrets redacted."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def scrub_obj(obj):
    """Recursively scrub every string inside a JSON-compatible structure."""
    if isinstance(obj, str):
        return scrub_text(obj)
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    return obj


def find_leaks(text: str) -> Dict[str, int]:
    """Report anything that survived scrubbing. Empty dict means clean."""
    leaks = {}
    for name, pattern in (
        ("home path", re.compile(r"/home/[A-Za-z0-9_.-]+")),
        ("users path", re.compile(r"/Users/[A-Za-z0-9_.-]+")),
        ("api key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ):
        count = len(pattern.findall(text))
        if count:
            leaks[name] = count
    return leaks


def assert_clean(text: str, label: str = "artifact") -> None:
    """Raise if anything sensitive survived. Last line of defence before write."""
    leaks = find_leaks(text)
    if leaks:
        detail = ", ".join(f"{n} x{c}" for n, c in leaks.items())
        raise ValueError(f"{label} still contains sensitive content: {detail}")
