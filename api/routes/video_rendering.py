from flask import Blueprint, jsonify, current_app, request, Response, send_from_directory, redirect
import subprocess
import os
import re
import json
import sys
import hashlib
import traceback
import shutil
import tempfile
from typing import Union
import uuid
import time
import requests
from pathlib import Path

from api.pipeline.llm import (  # re-exported: callers and tests import these here
    CodeGenerationError,
    LLMResult,
    generate_code,
    has_api_key,
    resolve_model,
)

video_rendering_bp = Blueprint("video_rendering", __name__)


def use_local_storage() -> bool:
    """Read at call time so tests and deployments can flip it via the environment."""
    return os.getenv("USE_LOCAL_STORAGE", "true").lower() in ("true", "1", "yes")


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8080")

def extract_code_from_markdown(raw_code: str) -> str:
    """提取 Markdown 中的代码块"""
    match = re.search(r"```(?:python)?\n(.*?)```", raw_code, re.DOTALL)
    code = match.group(1) if match else raw_code
    return code.strip()


def upload_to_azure_storage(file_path: str, video_storage_file_name: str) -> str:
    """
    Uploads the video to Azure Blob Storage and returns the URL.
    """
    from azure.storage.blob import BlobServiceClient  # optional dependency

    cloud_file_name = f"{video_storage_file_name}.mp4"

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=cloud_file_name
    )
    # Upload the video file
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    # Construct the URL of the uploaded blob
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{cloud_file_name}"
    return blob_url

def upload_to_google_storage(file_path: str, video_storage_file_name: str) -> str:
    """
    Uploads the video to google Storage and returns the URL.
    """
    from google.cloud import storage  # optional dependency

    cloud_file_name = f"{video_storage_file_name}.mp4"
    json_file = os.getenv("GOOGLE_CLOUD_FILE")
    bucket_name = os.getenv("GOOGLE_BUCKET_NAME")
    client = storage.Client.from_service_account_json(json_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(cloud_file_name)
    blob.upload_from_filename(file_path)
    return blob.public_url

def safe_storage_name(name: str) -> str:
    """Reduce a caller-supplied name to something safe to use as a filename.

    user_id / project_name come straight from the request body, so a value like
    "../../etc/cron.d/x" would otherwise escape the output directory.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", name).lstrip(".-")
    return cleaned[:120] or "video"


def move_to_public_folder(
    file_path: str, video_storage_file_name: str, base_url: Union[str, None] = None
) -> str:
    """
    Moves the video to the public folder and returns the URL.
    """
    video_storage_file_name = safe_storage_name(video_storage_file_name)
    # Must match the Flask static folder configured in api/__init__.py
    # (static_folder="public", static_url_path="/public"), which resolves to
    # api/public -- not api/routes/public.
    public_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
    os.makedirs(public_folder, exist_ok=True)

    new_file_name = f"{video_storage_file_name}.mp4"
    new_file_path = os.path.join(public_folder, new_file_name)

    shutil.move(file_path, new_file_path)

    # Use the provided base_url if available, otherwise fall back to BASE_URL
    url_base = base_url if base_url else BASE_URL
    video_url = f"{url_base.rstrip('/')}/public/{new_file_name}"
    return video_url


# width ratio, height ratio, Manim frame width (in scene units)
ASPECT_RATIOS = {
    "16:9": (16, 9, 14.22),
    "9:16": (9, 16, 8.0),
    "1:1": (1, 1, 8.0),
}

# Pixel length of the *short* edge. "ultra" reproduces the original 4K 16:9 output.
QUALITY_SHORT_EDGE = {"low": 480, "medium": 720, "high": 1080, "ultra": 2160}

DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_QUALITY = "high"


def get_frame_config(aspect_ratio=None, quality=None):
    """Return ((pixel_width, pixel_height), frame_width) for a shape and size.

    Aspect ratio controls shape only; quality controls resolution. Dimensions are
    forced even because H.264 cannot encode odd width/height.
    """
    w_ratio, h_ratio, frame_width = ASPECT_RATIOS.get(
        aspect_ratio or DEFAULT_ASPECT_RATIO, ASPECT_RATIOS[DEFAULT_ASPECT_RATIO]
    )
    short_edge = QUALITY_SHORT_EDGE.get(
        quality or DEFAULT_QUALITY, QUALITY_SHORT_EDGE[DEFAULT_QUALITY]
    )

    if w_ratio >= h_ratio:  # landscape or square: height is the short edge
        pixel_height = short_edge
        pixel_width = round(short_edge * w_ratio / h_ratio)
    else:  # portrait: width is the short edge
        pixel_width = short_edge
        pixel_height = round(short_edge * h_ratio / w_ratio)

    # Round up to even: 16:9 at 480 is 853.33px wide, and 854 is the conventional
    # 480p widescreen width. H.264 cannot encode odd dimensions.
    return (pixel_width + pixel_width % 2, pixel_height + pixel_height % 2), frame_width

def load_domain_config(domain: str = "default"):
    """Load domain configuration from JSON file"""
    config_dir = Path(__file__).parent.parent.parent / "config" / "domains"
    config_file = config_dir / f"{domain}.json"
    
    if not config_file.exists():
        config_file = config_dir / "default.json"
    
    with open(config_file, 'r') as f:
        return json.load(f)

# Raw, non-f string on purpose: this prompt contains literal LaTeX braces ({},
# \text{}, "Extra }") and backslash escapes, all of which are syntax errors inside
# an f-string. Domain values are substituted via the <<...>> markers below, which
# cannot collide with the LaTeX $, %, and {} that appear throughout the text.
_SYSTEM_PROMPT_TEMPLATE = r"""
        <<SYSTEM_PROMPT>>
        Manim is a mathematical animation engine that is used to create videos programmatically.

<<SCENE_GUIDE>>

        *Target: <<TARGET_TEMPLATE>>*

        **Video Structure Template:**
        1. **Concept Definition (2-8 seconds)**  
           - Provide a clear and concise explanation using Tex() (no special characters like $, %, &, _ unless escaped).  
           - Style: `.scale_to_fit_width(config.frame_width * 0.9)`
        
        2. **Formula Breakdown Scene (5-10 seconds)**
           - Use MathTex() for mathematical formulas.
           - All LaTeX symbols must be valid and safely escaped (e.g., use \$, \%, \_, \&, avoid malformed braces {}).
           - Avoid ambiguous math expressions (ensure \frac, \sum, \text{} syntax is correct).
            
        3. **Chart or Graph**
           - If a diagram is needed (e.g., number line, axes chart, grouped dots/lines), use Manim primitives like `NumberLine`, `Axes`, `VGroup(Dot(), Line())`.  
           - Position with reasonable spacing from the formula.  
           - Style: `.scale(0.7).to_edge(DOWN)`
           
        4. **Real-World Case Study (5-15 seconds)**  
           - Include one step-by-step numerical case to apply the formula. 
           - Show duration calculation process with actual numbers
           
        5. **Summary or Key Takeaway (2-8 seconds)**  
           - Key takeaways bullet points with highlight effects  
           - Common mistake alerts (e.g., "Remember: Modified duration ≠ Macaulay duration!")  
           - Exam-style question teaser with answer delayed to video end
           - Style: `.scale_to_fit_width(config.frame_width * 0.9)`
           
        # Important formatting constraints:
        1. Each section should appear sequentially on a clean screen, not overlaid on a single frame.
        2. Use clear() or fade_out() between sections to avoid visual clutter.
        3. Use only LaTeX expressions that are valid inside MathTex. Avoid alignment characters like &, and ensure all equations are properly wrapped.
        4. Avoid LaTeX compilation errors such as:
            - Misplaced alignment tab character &
            - Missing $ inserted
            - Undefined control sequence
            - Extra } or forgotten $
        5. If using long formulas, ensure they fit within the screen or apply .scale() or scale_to_fit_width() to prevent overflow.
        6. Text and math should not overlap. Use next_to(), to_edge(), or .shift() to properly place each object.
        7. Do not use any nonexistent methods like axes.get_bar(). Use standard BarChart or build bars with Rectangle and Axes.c2p.
        8. Never use raw $, %, &, #, ~, _, or ^ unless escaped properly.
        9. Ensure that all Text or MathTex objects fit within the screen boundaries
        10. Avoid "Missing $ inserted" errors — ensure all inline math is enclosed within proper math delimiters (e.g., \\( ... \\) or $...$).

        # Rules
        1. <<TRANSLATION_RULE>>
        2. Always use GenScene as the class name, otherwise, the code will not work.
        3. Always use self.play() to play the animation, otherwise, the code will not work.
        4. Do not use text to explain the code, only the code.
        5. Do not explain the code, only the code.
    """


_PLAIN_SCENE_GUIDE = r"""
        The following is an example of the code:
        ```
        from manim import *
        from math import *

        class GenScene(Scene):
            def construct(self):
                c = Circle(color=BLUE)
                self.play(Create(c))
        ```
"""

_VOICEOVER_SCENE_GUIDE = r"""
        The video must be narrated. The following is an example of the code:
        ```
        from manim import *
        from math import *
        from manim_voiceover import VoiceoverScene
        from manim_voiceover.services.gtts import GTTSService

        class GenScene(VoiceoverScene):
            def construct(self):
                self.set_speech_service(GTTSService(lang="en"))
                c = Circle(color=BLUE)
                with self.voiceover(text="Here is a blue circle.") as tracker:
                    self.play(Create(c), run_time=tracker.duration)
        ```

        # Narration rules
        1. GenScene must extend VoiceoverScene, and the first statement in
           construct() must be self.set_speech_service(GTTSService(lang="en")).
        2. Every self.play() call belongs inside a
           `with self.voiceover(text="...") as tracker:` block, and must pass
           run_time=tracker.duration so the visuals last as long as the narration.
        3. Narration text is spoken aloud, so write plain English prose only.
           No LaTeX, no markdown, no symbols: say "a squared plus b squared"
           rather than "a^2 + b^2", and "percent" rather than "%".
        4. Keep each narration segment to one or two short sentences and UNDER
           250 CHARACTERS. This is a hard limit: the text-to-speech endpoint
           rejects longer strings and the render fails. Split long explanations
           across several voiceover blocks, each wrapping its own animation.
        5. Call self.wait() only outside voiceover blocks.
        6. Aim for 6 to 10 voiceover blocks in total.
"""


def build_system_prompt(domain: str = "default", voiceover: bool = True) -> str:
    config = load_domain_config(domain)
    guide = _VOICEOVER_SCENE_GUIDE if voiceover else _PLAIN_SCENE_GUIDE
    return (
        _SYSTEM_PROMPT_TEMPLATE
        .replace("<<SCENE_GUIDE>>", guide)
        .replace("<<SYSTEM_PROMPT>>", config["system_prompt"])
        .replace("<<TARGET_TEMPLATE>>", config["target_template"])
        .replace("<<TRANSLATION_RULE>>", config["translation_rule"])
    )


def generate_llm_result(
    prompt_content: str,
    model: Union[str, None] = None,
    domain: str = "default",
    voiceover: bool = True,
) -> LLMResult:
    """Generate Manim source, carrying model / latency / token usage with it."""
    return generate_code(build_system_prompt(domain, voiceover), prompt_content, model)


def generate_llm_code(
    prompt_content: str,
    model: Union[str, None] = None,
    domain: str = "default",
    voiceover: bool = True,
) -> str:
    """Return just the source, for callers that don't need usage accounting."""
    return generate_llm_result(prompt_content, model, domain, voiceover).text

class RenderError(RuntimeError):
    """Raised when Manim fails to produce a video. Carries the render log."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


def build_scene_source(
    code: str,
    aspect_ratio: Union[str, None] = None,
    quality: Union[str, None] = None,
    voiceover: bool = False,
) -> str:
    """Wrap generated code with the Manim config for the requested aspect ratio.

    The config assignments come first; the scene's own `from manim import *`
    rebinds the name `config` to the very same ManimConfig singleton, so these
    values survive and are read when the scene is rendered.
    """
    (pixel_width, pixel_height), frame_width = get_frame_config(aspect_ratio, quality)
    header = (
        "from manim import config\n"
        f"config.pixel_width = {pixel_width}\n"
        f"config.pixel_height = {pixel_height}\n"
        f"config.frame_width = {frame_width}\n"
    )
    if voiceover:
        # Suppress the .srt sidecar manim_voiceover writes alongside the video.
        # Applied here rather than trusting the model to emit it.
        header += (
            "from manim.scene.scene_file_writer import SceneFileWriter\n"
            "SceneFileWriter.write_subcaption_file = lambda *a, **k: None\n"
        )
    return f"{header}\n{extract_code_from_markdown(code)}\n"


def _find_rendered_mp4(media_dir: Path, file_class: str) -> Path:
    """Locate the MP4 Manim produced, tolerating layout differences across versions."""
    direct = media_dir / f"{file_class}.mp4"
    if direct.exists():
        return direct
    candidates = sorted(
        media_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if candidates:
        return candidates[0]
    raise RenderError(f"Manim exited successfully but produced no .mp4 under {media_dir}")


def iter_render_scene(
    code: str,
    file_class: str = "GenScene",
    aspect_ratio: Union[str, None] = None,
    workdir: Union[str, None] = None,
    quality: Union[str, None] = None,
    voiceover: bool = False,
):
    """Render `code` to an MP4, yielding progress dicts and finally {"video_path": ...}.

    Raises RenderError (with the captured log) if Manim fails. On success the
    returned path lives inside `workdir`, so the caller owns cleanup; a workdir
    created here is only removed automatically when the render fails.
    """
    owns_workdir = workdir is None
    workdir = Path(workdir or tempfile.mkdtemp(prefix="genmanim-"))
    workdir.mkdir(parents=True, exist_ok=True)
    scene_path = workdir / "scene.py"
    media_dir = workdir / "media"
    scene_path.write_text(
        build_scene_source(code, aspect_ratio, quality, voiceover), encoding="utf-8"
    )

    command = [
        "manim",
        "render",
        str(scene_path),
        file_class,
        "--format=mp4",
        "--media_dir",
        str(media_dir),
        "--custom_folders",
        "--disable_caching",
    ]

    # stderr is merged into stdout: reading two pipes with alternating blocking
    # readline() calls deadlocks as soon as one stream is quiet, which is the
    # normal case for Manim (it logs progress to stderr only).
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(workdir),
        bufsize=0,
    )

    log_lines = []
    state = {"animation": -1, "percentage": 0}

    def parse(line: str):
        """Yield progress events for one line of Manim output."""
        log_lines.append(line)
        print("MANIM:", line, flush=True)

        animation_match = re.search(r"Animation (\d+):", line)
        if animation_match:
            new_animation = int(animation_match.group(1))
            if new_animation != state["animation"]:
                state["animation"] = new_animation
                state["percentage"] = 0
                yield {"animationIndex": new_animation, "percentage": 0}

        percentage_match = re.search(r"(\d+)%", line)
        if percentage_match:
            new_percentage = int(percentage_match.group(1))
            if new_percentage != state["percentage"]:
                state["percentage"] = new_percentage
                yield {
                    "animationIndex": state["animation"],
                    "percentage": new_percentage,
                }

    # Read the raw fd rather than iterating the stream: Manim draws progress with
    # carriage returns, so line iteration would withhold every update until the
    # render finished. os.read returns as soon as any bytes are available.
    fd = process.stdout.fileno()
    buffer = ""
    try:
        while True:
            data = os.read(fd, 4096)
            if not data:
                break
            buffer += data.decode("utf-8", errors="replace")
            parts = re.split(r"[\r\n]", buffer)
            buffer = parts.pop()
            for part in parts:
                if part.strip():
                    yield from parse(part)
        if buffer.strip():
            yield from parse(buffer)
    finally:
        process.stdout.close()
        process.wait()

    log = "\n".join(log_lines)
    if process.returncode != 0:
        if owns_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        raise RenderError(f"Manim exited with code {process.returncode}", log)

    yield {"video_path": str(_find_rendered_mp4(media_dir, file_class))}


def publish_video(
    video_file_path: str, video_storage_file_name: str, base_url: Union[str, None] = None
) -> str:
    """Move the rendered file to its final home and return a URL for it."""
    if use_local_storage():
        return move_to_public_folder(video_file_path, video_storage_file_name, base_url)
    return upload_to_google_storage(video_file_path, video_storage_file_name)


@video_rendering_bp.route("/v1/video/rendering", methods=["POST"])
def render_video():
    body = request.json or {}
    prompt_content = body.get("prompt", "")
    # None -> resolve_model() picks based on which provider key is configured
    model = body.get("model")
    domain = body.get("domain", "default")
    file_class = body.get("file_class", "GenScene")
    user_id = body.get("user_id") or str(uuid.uuid4())
    project_name = body.get("project_name")
    iteration = body.get("iteration")
    # Aspect Ratio can be: "16:9" (default), "1:1", "9:16"
    aspect_ratio = body.get("aspect_ratio")
    # low | medium | high | ultra -- see QUALITY_SHORT_EDGE
    quality = body.get("quality")
    # Narration is on by default; gTTS needs network access at render time.
    voiceover = body.get("voiceover", True)
    stream = body.get("stream", False)

    video_storage_file_name = f"video-{user_id}-{project_name}-{iteration}"
    # Captured here so the streaming generator never touches the request context.
    base_url = request.host_url

    try:
        code = generate_llm_code(prompt_content, model, domain, voiceover)
    except CodeGenerationError as e:
        return jsonify({"error": str(e)}), 502

    def events():
        workdir = tempfile.mkdtemp(prefix="genmanim-")
        try:
            for event in iter_render_scene(
                code, file_class, aspect_ratio, workdir, quality, voiceover
            ):
                if "video_path" in event:
                    video_url = publish_video(
                        event["video_path"], video_storage_file_name, base_url
                    )
                    yield {"message": "Video generation completed", "video_url": video_url}
                else:
                    yield event
        except RenderError as e:
            yield {"error": str(e), "log": e.log}
        except Exception as e:
            traceback.print_exc()
            yield {"error": f"Unexpected error occurred: {e}"}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    if stream:
        def ndjson():
            for event in events():
                yield json.dumps(event) + "\n"
                sys.stdout.flush()

        return Response(ndjson(), content_type="text/event-stream", status=207)

    result = None
    for event in events():
        if "video_url" in event or "error" in event:
            result = event
    if result is None:
        return jsonify({"error": "Renderer produced no result"}), 500
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result), 200


@video_rendering_bp.route("/v1/video/exporting", methods=["POST"])
def export_video():
    scenes = request.json.get("scenes")
    title_slug = request.json.get("titleSlug")
    local_filenames = []

    # Download each scene
    for scene in scenes:
        video_url = scene["videoUrl"]
        object_name = video_url.split("/")[-1]
        local_filename = download_video(video_url)
        local_filenames.append(local_filename)

    # Create a list of input file arguments for ffmpeg
    input_files = " ".join([f"-i {filename}" for filename in local_filenames])

    # Generate a unique filename with UNIX timestamp
    timestamp = int(time.time())
    merged_filename = os.path.join(
        os.getcwd(), f"exported-scene-{title_slug}-{timestamp}.mp4"
    )

    # Command to merge videos using ffmpeg
    command = f"ffmpeg {input_files} -filter_complex 'concat=n={len(local_filenames)}:v=1:a=0[out]' -map '[out]' {merged_filename}"

    try:
        # Execute the ffmpeg command
        subprocess.run(command, shell=True, check=True)
        print("Videos merged successfully.")
        print(f"merged_filename: {merged_filename}")
        public_url = upload_to_azure_storage(
            merged_filename, f"exported-scene-{title_slug}-{timestamp}"
        )
        print(f"Video URL: {public_url}")
        return jsonify(
            {"status": "Videos merged successfully", "video_url": public_url}
        )
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg error: {e}")
        return jsonify({"error": "Failed to merge videos"}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


def download_video(video_url):
    local_filename = video_url.split("/")[-1]
    response = requests.get(video_url)
    response.raise_for_status()
    with open(local_filename, 'wb') as f:
        f.write(response.content)
    return local_filename

def to_fixed_hash(s: str, length: int = 32) -> str:
    # 生成 64 位 hex（32字节），然后截取所需长度
    hash_val = hashlib.md5(s.encode()).hexdigest()
    return hash_val[:length]


def str_to_bool(value):
    return value.lower() in ('true', '1', 'yes')

@video_rendering_bp.route("/v1/video/play", methods=["GET"])
def run_manim_render():
    """Render a prompt to video via GET, reusing a cached copy when one exists.

    `save=true` (the default) reuses a previously rendered video for the same
    prompt instead of paying for a new LLM call and render.
    """
    prompt = request.args.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    save = str_to_bool(request.args.get("save", default="True"))
    model = request.args.get("model")
    domain = request.args.get("domain", "default")
    aspect_ratio = request.args.get("aspect_ratio")
    quality = request.args.get("quality")
    voiceover = str_to_bool(request.args.get("voiceover", default="True"))
    video_storage_file_name = to_fixed_hash(prompt)

    if save:
        cached = find_cached_video(video_storage_file_name, request.host_url)
        if cached:
            return jsonify({"video_url": cached}), 200

    try:
        code = generate_llm_code(prompt, model, domain, voiceover)
    except CodeGenerationError as e:
        return jsonify({"error": str(e)}), 502

    workdir = tempfile.mkdtemp(prefix="genmanim-")
    try:
        video_path = None
        for event in iter_render_scene(
            code, "GenScene", aspect_ratio, workdir, quality, voiceover
        ):
            if "video_path" in event:
                video_path = event["video_path"]
        if not video_path:
            return jsonify({"error": "Renderer produced no video"}), 500
        video_url = publish_video(video_path, video_storage_file_name, request.host_url)
        return jsonify({"video_url": video_url}), 200
    except RenderError as e:
        return jsonify({"error": str(e), "log": e.log}), 500
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def find_cached_video(
    video_storage_file_name: str, base_url: Union[str, None] = None
) -> Union[str, None]:
    """Return a URL for an already-rendered video, or None if it isn't cached."""
    file_name = f"{video_storage_file_name}.mp4"
    if use_local_storage():
        public_folder = Path(__file__).parent.parent / "public"
        if (public_folder / file_name).exists():
            url_base = (base_url or BASE_URL).rstrip("/")
            return f"{url_base}/public/{file_name}"
        return None

    from google.cloud import storage  # optional dependency

    bucket_name = os.getenv("GOOGLE_BUCKET_NAME")
    client = storage.Client.from_service_account_json(os.getenv("GOOGLE_CLOUD_FILE"))
    blob = client.bucket(bucket_name).blob(file_name)
    if blob.exists():
        return f"https://storage.googleapis.com/{bucket_name}/{file_name}"
    return None