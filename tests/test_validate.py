"""Pre-flight scene validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.validate import (  # noqa: E402
    MAX_NARRATION_CHARS,
    check_narration,
    check_scene_class,
    check_syntax,
    validate_scene,
)

GOOD = '''
from manim import *
from manim_voiceover import VoiceoverScene

class GenScene(VoiceoverScene):
    def construct(self):
        with self.voiceover(text="A short line of narration.") as tracker:
            self.play(Create(Circle()), run_time=tracker.duration)
'''


def test_good_scene_passes():
    assert validate_scene(GOOD) == []


def test_syntax_error_is_caught():
    problems = check_syntax("def broken(:\n    pass")
    assert problems and "does not parse" in problems[0]


def test_syntax_error_short_circuits_other_checks():
    """Reporting a missing class on unparseable code is noise."""
    problems = validate_scene("class GenScene(:\n")
    assert len(problems) == 1
    assert "does not parse" in problems[0]


def test_missing_scene_class_is_caught():
    problems = check_scene_class("class SomethingElse:\n    pass")
    assert problems and "GenScene not defined" in problems[0]
    assert "SomethingElse" in problems[0]


def test_overlong_narration_is_caught():
    """The real constraint: Google's TTS endpoint rejects long strings."""
    long_text = "Bond prices move inversely with yields. " * 20
    code = f'with self.voiceover(text="{long_text}") as tracker:'
    problems = check_narration(code)
    assert problems and "over the" in problems[0]


def test_narration_at_the_limit_passes():
    code = f'with self.voiceover(text="{"x" * MAX_NARRATION_CHARS}") as t:'
    assert check_narration(code) == []


def test_empty_narration_is_caught():
    assert check_narration('with self.voiceover(text="") as t:')


def test_each_overlong_block_is_reported():
    long_text = "y" * (MAX_NARRATION_CHARS + 50)
    code = (
        f'with self.voiceover(text="{long_text}") as t:\n'
        f'with self.voiceover(text="{long_text}") as t:\n'
    )
    assert len(check_narration(code)) == 2


def test_triple_quoted_narration_is_inspected():
    long_text = "z" * (MAX_NARRATION_CHARS + 10)
    code = f'with self.voiceover(text="""{long_text}""") as t:'
    assert check_narration(code)


def test_narration_ignored_when_voiceover_disabled():
    long_text = "w" * (MAX_NARRATION_CHARS + 10)
    code = (
        "class GenScene:\n    pass\n"
        f'# with self.voiceover(text="{long_text}")'
    )
    assert validate_scene(code, voiceover=False) == []
