"""Tests for the pipeline orchestrator, retry loop, and scrubber."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.llm import LLMResult  # noqa: E402
from api.pipeline.run import run_pipeline  # noqa: E402
from api.pipeline.scrub import (  # noqa: E402
    assert_clean,
    find_leaks,
    scrub_obj,
    scrub_text,
)

GOOD_CODE = """from manim import *

class GenScene(Scene):
    def construct(self):
        self.play(Create(Circle()))
"""


def code_with(snippet: str) -> str:
    """A valid scene carrying an extra line, so validation passes."""
    return GOOD_CODE + f"\n# {snippet}\n"


class FakeRenderError(Exception):
    def __init__(self, msg, log=""):
        super().__init__(msg)
        self.log = log


def make_generate(*texts):
    """Return a generate() stub yielding the given sources in order."""
    remaining = list(texts)
    calls = []

    def generate(prompt, model=None, domain="default", voiceover=True):
        calls.append(prompt)
        return LLMResult(
            text=remaining.pop(0), model="claude-opus-5", latency_ms=1000,
            input_tokens=100, output_tokens=200,
        )

    generate.calls = calls
    return generate


def make_render(*outcomes):
    """Each outcome is either None (succeed) or an exception to raise."""
    remaining = list(outcomes)

    def render(code, file_class, aspect_ratio, workdir, quality, voiceover):
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        yield {"animationIndex": 0, "percentage": 50}
        yield {"video_path": "/tmp/fake/GenScene.mp4"}

    return render


def drain(gen):
    events, result = [], None
    for event in gen:
        if "result" in event:
            result = event["result"]
        else:
            events.append(event)
    return events, result


# --- happy path ----------------------------------------------------------


def test_successful_run_records_all_stages(tmp_path):
    events, result = drain(run_pipeline(
        "a circle", "demo",
        generate=make_generate(GOOD_CODE), render=make_render(None),
        workdir=str(tmp_path),
    ))

    assert result.attempts == 1
    assert result.video_path.endswith(".mp4")
    stages = [e.stage for e in result.recorder.events]
    assert stages == ["code_generation", "code_generation", "sanitize",
                      "validate", "render", "done"]


def test_progress_events_pass_through(tmp_path):
    events, _ = drain(run_pipeline(
        "a circle", "demo",
        generate=make_generate(GOOD_CODE), render=make_render(None),
        workdir=str(tmp_path),
    ))
    assert any("percentage" in e for e in events)


def test_usage_is_totalled_across_calls(tmp_path):
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=make_generate(GOOD_CODE), render=make_render(None),
        workdir=str(tmp_path),
    ))
    meta = result.to_meta()
    assert meta["input_tokens"] == 100
    assert meta["output_tokens"] == 200
    assert meta["cost_cents"] == pytest.approx(0.55)  # (100*5 + 200*25)/1e6*100


# --- retry ---------------------------------------------------------------


def test_render_failure_triggers_repair_and_succeeds(tmp_path):
    """The headline behaviour: a failed render is fixed and re-rendered."""
    generate = make_generate(GOOD_CODE, "from manim import *  # fixed\n")
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=generate,
        render=make_render(FakeRenderError("boom", log="Undefined control sequence"), None),
        workdir=str(tmp_path),
    ))

    assert result.attempts == 2
    assert "fixed" in result.code
    # Second call must carry the error and the failing source back to the model.
    assert "Undefined control sequence" in generate.calls[1]
    assert "from manim import *" in generate.calls[1]


def test_retry_emits_error_and_warn_events(tmp_path):
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=make_generate(GOOD_CODE, GOOD_CODE),
        render=make_render(FakeRenderError("boom", log="ValueError: bad"), None),
        workdir=str(tmp_path),
    ))
    levels = {e.level for e in result.recorder.events}
    assert "error" in levels and "warn" in levels


def test_gives_up_after_max_attempts(tmp_path):
    boom = [FakeRenderError("boom", log="ValueError: bad") for _ in range(3)]
    with pytest.raises(FakeRenderError):
        drain(run_pipeline(
            "a circle", "demo",
            generate=make_generate(GOOD_CODE, GOOD_CODE, GOOD_CODE),
            render=make_render(*boom),
            workdir=str(tmp_path), max_attempts=3,
        ))


def test_transient_failure_rerenders_without_calling_the_model(tmp_path):
    """gTTS rate-limiting is not something the model can fix -- don't pay for it."""
    generate = make_generate(GOOD_CODE)  # only one source: a repair call would IndexError
    slept = []
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=generate,
        render=make_render(
            FakeRenderError("boom", log="Exception: gTTS gave an error. You are either"),
            None,
        ),
        workdir=str(tmp_path), sleep=slept.append,
    ))

    assert result.attempts == 2
    assert len(generate.calls) == 1, "transient failure must not trigger a repair call"
    assert slept, "should back off before re-rendering"
    assert any("transient" in e.msg for e in result.recorder.events)


def test_code_failure_still_triggers_repair(tmp_path):
    """The classifier must not swallow genuine scene errors."""
    generate = make_generate(GOOD_CODE, GOOD_CODE)
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=generate,
        render=make_render(
            FakeRenderError("boom", log="Undefined control sequence \\frac"), None
        ),
        workdir=str(tmp_path), sleep=lambda _: None,
    ))
    assert len(generate.calls) == 2
    assert any("asking model to fix" in e.msg for e in result.recorder.events)


def test_repair_output_is_also_sanitized(tmp_path):
    """A model fixing LaTeX often reintroduces typographic characters."""
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=make_generate(GOOD_CODE, code_with('Tex("a — b")')),
        render=make_render(FakeRenderError("boom", log="err"), None),
        workdir=str(tmp_path),
    ))
    assert "—" not in result.code


# --- sanitize integration ------------------------------------------------


def test_sanitize_warns_when_it_rewrites(tmp_path):
    _, result = drain(run_pipeline(
        "a circle", "demo",
        generate=make_generate(code_with('Tex("a — b")')), render=make_render(None),
        workdir=str(tmp_path),
    ))
    sanitize_events = [e for e in result.recorder.events if e.stage == "sanitize"]
    assert sanitize_events[0].level == "warn"
    assert "unicode dashes" in sanitize_events[0].msg


# --- scrubbing -----------------------------------------------------------


def test_home_paths_are_rewritten():
    assert scrub_text("/home/ryan/Generative-Manim-Template/x.py").startswith("~/")


def test_workdir_paths_are_rewritten():
    assert scrub_text("/tmp/genmanim-ab12/media/GenScene.mp4").startswith("<workdir>")


@pytest.mark.parametrize("secret", [
    "sk-ant-api03-" + "x" * 40,
    "sk-" + "y" * 40,
])
def test_keys_are_redacted(secret):
    assert secret not in scrub_text(f"Authorization: Bearer {secret}")


def test_scrub_recurses_into_structures():
    obj = {"events": [{"msg": "wrote /home/ryan/out.mp4"}], "n": 3}
    cleaned = scrub_obj(obj)
    assert cleaned["events"][0]["msg"] == "wrote ~/out.mp4"
    assert cleaned["n"] == 3


def test_find_leaks_reports_survivors():
    assert find_leaks("/home/ryan/x") == {"home path": 1}
    assert find_leaks("clean text") == {}


def test_assert_clean_raises_on_leak():
    with pytest.raises(ValueError, match="sensitive"):
        assert_clean("/home/ryan/secret.py", "scene.py")


def test_assert_clean_passes_scrubbed_text():
    assert_clean(scrub_text("/home/ryan/x and sk-" + "z" * 40))
