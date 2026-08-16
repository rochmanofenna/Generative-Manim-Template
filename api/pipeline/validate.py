"""Pre-flight checks on generated scenes.

Catches defects that would otherwise surface only after paying for a render.
The narration length limit is not arbitrary: Google's TTS endpoint rejects
overly long text outright, and a single oversized voiceover block fails the
whole render several seconds in.
"""

import ast
import re
from typing import List

# 30 sentences (~1200 chars) synthesises fine; 60 does not. 250 keeps each
# segment well inside that and produces better pacing on screen anyway.
MAX_NARRATION_CHARS = 250

_VOICEOVER_TEXT = re.compile(
    r"""voiceover\s*\(\s*text\s*=\s*(?P<q>["']{1,3})(?P<text>.*?)(?P=q)""",
    re.DOTALL,
)


def check_syntax(code: str) -> List[str]:
    """Reject code Python cannot even parse, before invoking Manim."""
    try:
        ast.parse(code)
    except SyntaxError as e:
        return [f"scene does not parse: line {e.lineno}: {e.msg}"]
    return []


def check_scene_class(code: str, class_name: str = "GenScene") -> List[str]:
    """The renderer targets a class by name; its absence is a guaranteed failure."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # check_syntax already reported this
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    if class_name not in names:
        found = ", ".join(sorted(names)) or "none"
        return [f"class {class_name} not defined (found: {found})"]
    return []


def check_narration(code: str) -> List[str]:
    """Flag voiceover blocks whose text is too long for the TTS endpoint."""
    problems = []
    for match in _VOICEOVER_TEXT.finditer(code):
        text = match.group("text").strip()
        if not text:
            problems.append("a voiceover block has empty narration text")
        elif len(text) > MAX_NARRATION_CHARS:
            problems.append(
                f"narration block is {len(text)} chars, over the "
                f"{MAX_NARRATION_CHARS} limit: {text[:60]!r}..."
            )
    return problems


def validate_scene(code: str, voiceover: bool = True) -> List[str]:
    """Return every problem found. An empty list means the scene is renderable."""
    problems = check_syntax(code)
    if problems:
        return problems  # nothing else is meaningful on unparseable code
    problems += check_scene_class(code)
    if voiceover:
        problems += check_narration(code)
    return problems
