"""Tests for the Manim render pipeline.

The pure tests run anywhere. The tests marked `render` shell out to Manim and are
skipped automatically when it is not installed.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.routes.video_rendering import (  # noqa: E402
    CodeGenerationError,
    RenderError,
    build_scene_source,
    build_system_prompt,
    extract_code_from_markdown,
    generate_llm_code,
    get_frame_config,
    iter_render_scene,
    move_to_public_folder,
    resolve_model,
)

manim_required = pytest.mark.skipif(
    shutil.which("manim") is None, reason="manim is not installed"
)


@pytest.fixture(autouse=True)
def no_live_api_calls(monkeypatch):
    """Strip provider keys from every test.

    create_app() calls load_dotenv(), so a real .env would otherwise let any test
    that forgets to stub the LLM make a billable call against the live API.
    Tests that need a key set one explicitly via monkeypatch.
    """
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEFAULT_MODEL"):
        monkeypatch.delenv(var, raising=False)

TRIVIAL_SCENE = """
from manim import *

class GenScene(Scene):
    def construct(self):
        c = Circle(color=BLUE)
        self.play(Create(c))
"""

BROKEN_SCENE = """
from manim import *

class GenScene(Scene):
    def construct(self):
        raise ValueError("deliberate failure")
"""

NARRATED_SCENE = """
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

class GenScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))
        c = Circle(color=BLUE)
        with self.voiceover(text="Here is a blue circle.") as tracker:
            self.play(Create(c), run_time=tracker.duration)
"""


# --- prompt construction -------------------------------------------------


def test_system_prompt_has_no_unresolved_markers():
    """Regression: the prompt used to be an f-string and was a SyntaxError."""
    prompt = build_system_prompt("default")
    assert "<<" not in prompt and ">>" not in prompt
    assert "GenScene" in prompt


def test_system_prompt_injects_domain_config():
    physics = build_system_prompt("physics")
    default = build_system_prompt("default")
    assert physics != default


def test_unknown_domain_falls_back_to_default():
    assert build_system_prompt("does-not-exist") == build_system_prompt("default")


def test_system_prompt_keeps_literal_latex_braces():
    prompt = build_system_prompt("default")
    assert r"\text{}" in prompt


# --- code extraction -----------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("```python\nfrom manim import *\n```", "from manim import *"),
        ("```\nfrom manim import *\n```", "from manim import *"),
        ("from manim import *", "from manim import *"),
    ],
)
def test_extract_code_from_markdown(raw, expected):
    assert extract_code_from_markdown(raw) == expected


# --- frame configuration -------------------------------------------------


@pytest.mark.parametrize(
    "aspect_ratio,quality,expected",
    [
        ("16:9", "high", (1920, 1080)),
        ("9:16", "high", (1080, 1920)),
        ("1:1", "high", (1080, 1080)),
        ("16:9", "ultra", (3840, 2160)),
        ("16:9", "low", (854, 480)),
        (None, None, (1920, 1080)),
        ("nonsense", None, (1920, 1080)),
    ],
)
def test_get_frame_config(aspect_ratio, quality, expected):
    (width, height), frame_width = get_frame_config(aspect_ratio, quality)
    assert (width, height) == expected
    assert frame_width > 0


def test_frame_dimensions_are_even_for_h264():
    for aspect_ratio in ("16:9", "9:16", "1:1"):
        for quality in ("low", "medium", "high", "ultra"):
            (width, height), _ = get_frame_config(aspect_ratio, quality)
            assert width % 2 == 0 and height % 2 == 0


def test_build_scene_source_applies_aspect_ratio():
    """Regression: aspect_ratio was computed and then never used."""
    source = build_scene_source(TRIVIAL_SCENE, "9:16", "high")
    assert "config.pixel_width = 1080" in source
    assert "config.pixel_height = 1920" in source
    assert "class GenScene" in source


def test_build_scene_source_strips_markdown_fence():
    source = build_scene_source("```python\nfrom manim import *\n```")
    assert "```" not in source


# --- narration -----------------------------------------------------------


def test_voiceover_prompt_asks_for_voiceover_scene():
    prompt = build_system_prompt("default", voiceover=True)
    assert "VoiceoverScene" in prompt
    assert "GTTSService" in prompt
    assert "tracker.duration" in prompt


def test_plain_prompt_has_no_narration_instructions():
    prompt = build_system_prompt("default", voiceover=False)
    assert "VoiceoverScene" not in prompt
    assert "class GenScene(Scene)" in prompt


def test_voiceover_source_suppresses_subcaption_file():
    source = build_scene_source(TRIVIAL_SCENE, "16:9", "low", voiceover=True)
    assert "write_subcaption_file" in source


def test_plain_source_omits_subcaption_patch():
    source = build_scene_source(TRIVIAL_SCENE, "16:9", "low", voiceover=False)
    assert "write_subcaption_file" not in source


@manim_required
def test_narrated_render_has_audible_audio_track(tmp_path):
    """The point of the feature: the MP4 carries a real, non-silent audio stream."""
    video_path = None
    try:
        for event in iter_render_scene(
            NARRATED_SCENE, "GenScene", "16:9", str(tmp_path),
            quality="low", voiceover=True,
        ):
            if "video_path" in event:
                video_path = Path(event["video_path"])
    except RenderError as e:
        # gTTS is an external, rate-limited service. Its being unreachable is
        # not a defect in this code, so don't report it as a test failure.
        if "gTTS" in e.log or "not connected to the internet" in e.log:
            pytest.skip("gTTS unavailable (offline or rate-limited)")
        raise

    assert video_path is not None and video_path.exists()

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type,codec_name", "-of", "json", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    assert streams, "rendered video has no audio stream"
    assert streams[0]["codec_type"] == "audio"

    # An audio stream can still be pure silence -- check it actually carries signal.
    loudness = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video_path), "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", loudness.stderr)
    assert match, f"volumedetect produced no reading: {loudness.stderr[-500:]}"
    assert float(match.group(1)) > -50.0, "audio track is effectively silent"


@manim_required
def test_silent_render_has_no_audio_track(tmp_path):
    video_path = None
    for event in iter_render_scene(
        TRIVIAL_SCENE, "GenScene", "16:9", str(tmp_path), quality="low", voiceover=False
    ):
        if "video_path" in event:
            video_path = Path(event["video_path"])

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "json", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(probe.stdout).get("streams", []) == []


# --- provider selection --------------------------------------------------


def test_explicit_model_wins(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert resolve_model("gpt-4o") == "gpt-4o"
    assert resolve_model("claude-opus-5") == "claude-opus-5"


def test_anthropic_key_alone_selects_claude(monkeypatch):
    """Regression: the render endpoint hardcoded gpt-4o and 401'd on an Anthropic key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "x" * 40)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    assert resolve_model().startswith("claude-")


def test_openai_key_selects_gpt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-" + "x" * 40)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    assert resolve_model() == "gpt-4o"


def test_placeholder_key_does_not_count_as_configured(monkeypatch):
    """Regression: a leftover 'sk-...' placeholder routed requests to OpenAI."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-...")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "x" * 40)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    assert resolve_model().startswith("claude-")


def test_default_model_env_overrides_detection(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("DEFAULT_MODEL", "claude-sonnet-5")
    assert resolve_model() == "claude-sonnet-5"


def _stub_result(text="from manim import *", model="claude-opus-5"):
    from api.pipeline.llm import LLMResult

    return LLMResult(text=text, model=model, latency_ms=1200,
                     input_tokens=100, output_tokens=200)


def test_claude_model_routes_to_anthropic(monkeypatch):
    import api.pipeline.llm as llm

    seen = {}

    def fake_anthropic(system_prompt, prompt_content, model):
        seen["model"] = model
        return _stub_result()

    def fail_openai(*args, **kwargs):
        raise AssertionError("claude-* must not reach the OpenAI path")

    monkeypatch.setattr(llm, "_generate_with_anthropic", fake_anthropic)
    monkeypatch.setattr(llm, "_generate_with_openai", fail_openai)

    assert generate_llm_code("a circle", "claude-opus-5") == "from manim import *"
    assert seen["model"] == "claude-opus-5"


def test_gpt_model_routes_to_openai(monkeypatch):
    import api.pipeline.llm as llm

    def fail_anthropic(*args, **kwargs):
        raise AssertionError("gpt-* must not reach the Anthropic path")

    monkeypatch.setattr(llm, "_generate_with_anthropic", fail_anthropic)
    monkeypatch.setattr(
        llm, "_generate_with_openai", lambda s, p, m: _stub_result(model="gpt-4o")
    )

    assert generate_llm_code("a circle", "gpt-4o") == "from manim import *"


def test_claude_refusal_raises_code_generation_error(monkeypatch):
    """A refusal returns HTTP 200 with empty content — it must not look like success."""
    import api.routes.video_rendering as vr

    class FakeResponse:
        stop_reason = "refusal"
        content = []

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    fake_module = type("m", (), {"Anthropic": FakeAnthropic})
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    with pytest.raises(CodeGenerationError, match="declined"):
        generate_llm_code("something", "claude-opus-5")


def test_anthropic_request_omits_temperature(monkeypatch):
    """temperature is rejected with a 400 on Claude Opus 5 and the 4.7+ family."""
    import api.routes.video_rendering as vr

    captured = {}

    class FakeBlock:
        type = "text"
        text = "from manim import *"

    class FakeResponse:
        stop_reason = "end_turn"
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        sys.modules, "anthropic", type("m", (), {"Anthropic": FakeAnthropic})
    )

    generate_llm_code("a circle", "claude-opus-5")
    assert "temperature" not in captured
    assert captured["max_tokens"] >= 8000, "too small a cap truncates generated scenes"


# --- storage -------------------------------------------------------------


def test_move_to_public_folder_targets_flask_static_dir(tmp_path):
    """Regression: files landed in api/routes/public, but Flask serves api/public."""
    src = tmp_path / "GenScene.mp4"
    src.write_bytes(b"not really a video")

    url = move_to_public_folder(str(src), "video-test", "http://localhost:8080")

    import api.routes.video_rendering as vr

    expected_dir = Path(vr.__file__).parent.parent / "public"
    written = expected_dir / "video-test.mp4"
    try:
        assert written.exists(), f"video was not written to {expected_dir}"
        assert url == "http://localhost:8080/public/video-test.mp4"
    finally:
        written.unlink(missing_ok=True)


def test_use_local_storage_reads_environment(monkeypatch):
    """Regression: USE_LOCAL_STORAGE was hardcoded to False."""
    import api.routes.video_rendering as vr

    monkeypatch.delenv("USE_LOCAL_STORAGE", raising=False)
    assert vr.use_local_storage() is True
    monkeypatch.setenv("USE_LOCAL_STORAGE", "false")
    assert vr.use_local_storage() is False
    monkeypatch.setenv("USE_LOCAL_STORAGE", "TRUE")
    assert vr.use_local_storage() is True


# --- rendering -----------------------------------------------------------


@manim_required
def test_render_produces_playable_mp4(tmp_path):
    """The whole point: a scene in, a real video file out."""
    video_path = None
    for event in iter_render_scene(
        TRIVIAL_SCENE, "GenScene", "16:9", str(tmp_path), quality="low"
    ):
        if "video_path" in event:
            video_path = Path(event["video_path"])

    assert video_path is not None, "renderer never reported a video_path"
    assert video_path.exists()
    assert video_path.suffix == ".mp4"
    assert video_path.stat().st_size > 1024

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name,nb_frames",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["width"] == 854 and stream["height"] == 480
    assert stream["codec_name"] == "h264"


@manim_required
def test_render_reports_progress(tmp_path):
    events = list(
        iter_render_scene(
            TRIVIAL_SCENE, "GenScene", "16:9", str(tmp_path), quality="low"
        )
    )
    progress = [e for e in events if "percentage" in e]
    assert progress, "expected at least one progress event"
    assert all(0 <= e["percentage"] <= 100 for e in progress)


@manim_required
def test_render_failure_raises_with_log(tmp_path):
    """Regression: failures were swallowed and returned HTTP 200."""
    with pytest.raises(RenderError) as excinfo:
        list(
            iter_render_scene(
                BROKEN_SCENE, "GenScene", "16:9", str(tmp_path), quality="low"
            )
        )
    assert "deliberate failure" in excinfo.value.log


@manim_required
def test_render_honours_portrait_aspect_ratio(tmp_path):
    video_path = None
    for event in iter_render_scene(
        TRIVIAL_SCENE, "GenScene", "9:16", str(tmp_path), quality="low"
    ):
        if "video_path" in event:
            video_path = Path(event["video_path"])

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert (stream["width"], stream["height"]) == (480, 854)


# --- HTTP endpoint -------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("USE_LOCAL_STORAGE", "true")
    from api import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_rendering_endpoint_returns_500_on_render_failure(client, monkeypatch):
    """Regression: every failure used to return 200 'no URL was found'."""
    import api.routes.video_rendering as vr

    monkeypatch.setattr(vr, "generate_llm_code", lambda *a, **k: TRIVIAL_SCENE)

    def boom(*args, **kwargs):
        raise RenderError("manim blew up", "traceback here")
        yield  # pragma: no cover - makes this a generator

    monkeypatch.setattr(vr, "iter_render_scene", boom)

    response = client.post("/v1/video/rendering", json={"prompt": "circle"})
    assert response.status_code == 500
    assert "manim blew up" in response.get_json()["error"]


def test_rendering_endpoint_returns_502_when_llm_fails(client, monkeypatch):
    """Regression: generate_llm_code returned a Flask tuple into re.search()."""
    import api.routes.video_rendering as vr

    def fail(*args, **kwargs):
        raise CodeGenerationError("no API key")

    monkeypatch.setattr(vr, "generate_llm_code", fail)

    response = client.post("/v1/video/rendering", json={"prompt": "circle"})
    assert response.status_code == 502
    assert "no API key" in response.get_json()["error"]


def test_missing_api_key_returns_502_not_traceback(client, monkeypatch):
    """Regression: OpenAI() was built outside the try, so a missing key 500'd."""
    # Both providers cleared: .env is loaded by create_app(), so leaving either
    # key in place would make this test spend real credits on a live call.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)

    response = client.post("/v1/video/rendering", json={"prompt": "circle"})
    assert response.status_code == 502
    assert "error" in response.get_json()


def test_rendering_endpoint_returns_video_url(client, monkeypatch, tmp_path):
    import api.routes.video_rendering as vr

    fake_video = tmp_path / "GenScene.mp4"
    fake_video.write_bytes(b"video bytes")

    monkeypatch.setattr(vr, "generate_llm_code", lambda *a, **k: TRIVIAL_SCENE)

    def fake_render(*args, **kwargs):
        yield {"animationIndex": 0, "percentage": 50}
        yield {"video_path": str(fake_video)}

    monkeypatch.setattr(vr, "iter_render_scene", fake_render)

    response = client.post("/v1/video/rendering", json={"prompt": "circle"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["video_url"].endswith(".mp4")

    served = Path(vr.__file__).parent.parent / "public" / Path(body["video_url"]).name
    try:
        assert served.exists()
    finally:
        served.unlink(missing_ok=True)


def test_streaming_endpoint_emits_ndjson(client, monkeypatch, tmp_path):
    import api.routes.video_rendering as vr

    fake_video = tmp_path / "GenScene.mp4"
    fake_video.write_bytes(b"video bytes")

    monkeypatch.setattr(vr, "generate_llm_code", lambda *a, **k: TRIVIAL_SCENE)

    def fake_render(*args, **kwargs):
        yield {"animationIndex": 0, "percentage": 25}
        yield {"video_path": str(fake_video)}

    monkeypatch.setattr(vr, "iter_render_scene", fake_render)

    response = client.post(
        "/v1/video/rendering", json={"prompt": "circle", "stream": True}
    )
    lines = [l for l in response.get_data(as_text=True).splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]

    assert events[0]["percentage"] == 25
    assert "video_url" in events[-1]

    served = Path(vr.__file__).parent.parent / "public" / Path(events[-1]["video_url"]).name
    served.unlink(missing_ok=True)
