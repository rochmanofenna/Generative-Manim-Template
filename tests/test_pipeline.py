"""Tests for run telemetry and source sanitizing."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.events import RunEvent, RunRecorder  # noqa: E402
from api.pipeline.llm import LLMResult  # noqa: E402
from api.pipeline.sanitize import (  # noqa: E402
    describe_rewrites,
    sanitize_code,
)


class FakeClock:
    """Monotonic clock returning scripted values, in seconds."""

    def __init__(self, *values):
        self._values = list(values)
        self._last = self._values[-1] if self._values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


# --- events --------------------------------------------------------------


def test_offsets_are_measured_from_run_start():
    """t_ms must be a real offset -- the demo page replays on these timings."""
    clock = FakeClock(100.0, 100.0, 103.82, 108.1)
    recorder = RunRecorder("demo", clock=clock)

    first = recorder.emit("code_generation", "calling model")
    second = recorder.emit("render", "manim started")

    assert first.t_ms == 0
    assert second.t_ms == 3820


def test_run_json_shape():
    clock = FakeClock(0.0, 0.0, 1.5)
    recorder = RunRecorder("fourier-square-wave", clock=clock)
    recorder.emit("code_generation", "start")
    recorder.emit("done", "out.mp4 4.2MB")

    payload = recorder.to_run_json()
    assert payload["slug"] == "fourier-square-wave"
    assert payload["total_ms"] == 1500
    assert [e["stage"] for e in payload["events"]] == ["code_generation", "done"]
    assert payload["started_at"].endswith("+00:00")


def test_total_ms_matches_last_event():
    clock = FakeClock(0.0, 0.0, 2.0)
    recorder = RunRecorder("demo", clock=clock)
    recorder.emit("code_generation", "a")
    last = recorder.emit("render", "b")
    assert recorder.to_run_json()["total_ms"] == last.t_ms


def test_unknown_stage_is_rejected():
    """The stage set is closed so a consumer can colour and group by it."""
    recorder = RunRecorder("demo")
    with pytest.raises(ValueError, match="unknown stage"):
        recorder.emit("storyboard", "not built yet")


def test_unknown_level_is_rejected():
    recorder = RunRecorder("demo")
    with pytest.raises(ValueError, match="unknown level"):
        recorder.emit("render", "oops", level="critical")


def test_warnings_and_errors_are_recorded_not_filtered():
    """A captured failure is the most valuable event in a run."""
    recorder = RunRecorder("demo")
    recorder.emit("render", "manim exited 1", level="error")
    recorder.emit("render", "retry 1/3", level="warn")

    levels = [e["level"] for e in recorder.to_run_json()["events"]]
    assert levels == ["error", "warn"]


def test_event_is_json_serialisable():
    import json

    event = RunEvent(t_ms=10, stage="render", level="info", msg="ok")
    assert json.loads(json.dumps(event.to_dict())) == event.to_dict()


# --- usage accounting ----------------------------------------------------


def test_cost_is_computed_from_token_counts():
    """Opus 5 is $5/MTok in, $25/MTok out."""
    result = LLMResult(
        text="x", model="claude-opus-5", latency_ms=1000,
        input_tokens=1_000_000, output_tokens=1_000_000,
    )
    # $5 + $25 = $30 = 3000 cents
    assert result.cost_cents == pytest.approx(3000.0)


def test_realistic_run_costs_a_fraction_of_a_cent():
    result = LLMResult(
        text="x", model="claude-opus-5", latency_ms=3800,
        input_tokens=1200, output_tokens=1800,
    )
    # (1200*5 + 1800*25) / 1e6 * 100 = 5.1 cents
    assert result.cost_cents == pytest.approx(5.1, abs=1e-6)


def test_unknown_model_reports_no_cost_rather_than_guessing():
    result = LLMResult(
        text="x", model="some-future-model", latency_ms=1000,
        input_tokens=100, output_tokens=100,
    )
    assert result.cost_cents is None


def test_missing_usage_reports_no_cost():
    result = LLMResult(text="x", model="claude-opus-5", latency_ms=1000)
    assert result.cost_cents is None


def test_summary_includes_model_latency_and_tokens():
    result = LLMResult(
        text="x", model="claude-opus-5", latency_ms=3820,
        input_tokens=1200, output_tokens=1240,
    )
    summary = result.summary()
    assert "claude-opus-5" in summary
    assert "3.8s" in summary
    assert "1240 completion tokens" in summary


def test_summary_degrades_without_usage():
    summary = LLMResult(text="x", model="mystery", latency_ms=500).summary()
    assert "mystery" in summary and "0.5s" in summary
    assert "tokens" not in summary


# --- sanitize ------------------------------------------------------------


def test_em_dash_is_rewritten():
    code, counts = sanitize_code('Tex("a — b")')
    assert "—" not in code
    assert counts == {"unicode dashes": 1}


def test_smart_quotes_are_rewritten():
    code, counts = sanitize_code('Tex("it’s a “test”")')
    assert "’" not in code and "“" not in code
    assert counts == {"smart quotes": 3}


def test_mixed_characters_are_grouped_by_label():
    code, counts = sanitize_code('Tex("a — b – c")\nTex("it’s")')
    assert counts == {"unicode dashes": 2, "smart quotes": 1}


def test_math_symbols_become_latex_commands():
    code, counts = sanitize_code('MathTex("a × b ≤ c")')
    assert r"\times" in code and r"\leq" in code
    assert counts == {"math symbols": 2}


def test_clean_code_is_untouched():
    original = 'from manim import *\nTex("plain ascii")'
    code, counts = sanitize_code(original)
    assert code == original
    assert counts == {}


def test_sanitised_code_is_ascii_encodable():
    """The point of the pass: pdflatex must be able to consume the result."""
    dirty = 'Tex("a — b’s “x” … 5 × 3 ≠ 2")'
    code, _ = sanitize_code(dirty)
    code.encode("ascii")  # raises UnicodeEncodeError on failure


def test_describe_rewrites_reads_as_a_log_line():
    assert describe_rewrites({"unicode dashes": 3}) == "3 unicode dashes rewritten"
    assert describe_rewrites({}) == "no rewrites needed"


def test_describe_rewrites_joins_multiple_groups():
    msg = describe_rewrites({"unicode dashes": 2, "smart quotes": 1})
    assert "2 unicode dashes" in msg and "1 smart quotes" in msg
