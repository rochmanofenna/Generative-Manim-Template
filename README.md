# Generative Manim

Turn a text prompt into a narrated educational video. An LLM writes a [Manim](https://www.manim.community/) scene, Manim renders it to MP4, and the result is served over HTTP.

```
User prompt
   │
   ▼
┌──────────────────────────────────────────┐
│  Flask app                               │
│  run.py → api/__init__.py:create_app()   │
└───────────────┬──────────────────────────┘
                │  POST /v1/video/rendering
                ▼
┌──────────────────────────────────────────┐
│  Code generation                         │
│  api/routes/video_rendering.py           │
│  - build_system_prompt()  domain + mode  │
│  - generate_llm_code()    Claude / GPT   │
└───────────────┬──────────────────────────┘
                │  Manim source (as text)
                ▼
┌──────────────────────────────────────────┐
│  Render                                  │
│  - build_scene_source()  inject config   │
│  - iter_render_scene()   run `manim`,    │
│    stream progress, locate the MP4       │
└───────────────┬──────────────────────────┘
                │  GenScene.mp4
                ▼
┌──────────────────────────────────────────┐
│  Publish                                 │
│  - publish_video()  local / GCS / Azure  │
└───────────────┬──────────────────────────┘
                ▼
        MP4 + video_url
```

## Features

- **Narrated by default** — gTTS voiceover via `manim-voiceover`, no API key needed
- **Multi-provider** — Anthropic Claude or OpenAI, selected automatically from whichever key is set
- **Domain configurable** — swap the system prompt per subject via `config/domains/*.json`
- **Aspect ratios and quality** — 16:9, 9:16, 1:1 at 480p through 4K
- **Streaming progress** — per-animation percentage over NDJSON
- **Pluggable storage** — local filesystem by default; Google Cloud Storage or Azure Blob optional

## Requirements

**Python 3.11.** Not 3.12+: `manim==0.18.0` pins `Pillow 9.5.0`, which publishes no wheels for 3.12 and fails to build against current libwebp.

System packages (not installed by pip):

- FFmpeg
- A LaTeX distribution providing `latex`, `pdflatex`, and `dvisvgm`
- cairo and pango

```bash
# Arch
sudo pacman -S --needed ffmpeg cairo pango texlive-basic texlive-latex \
                        texlive-latexextra texlive-fontsextra texlive-binextra

# Debian/Ubuntu
sudo apt install ffmpeg libcairo2-dev libpango1.0-dev \
                 texlive texlive-latex-extra texlive-fonts-extra dvisvgm
```

## Install

```bash
git clone <your-fork-url> generative-manim
cd generative-manim

uv venv --python 3.11 .venv          # or: python3.11 -m venv .venv
uv pip install --python .venv/bin/python -r api/requirements.txt
```

`manimpango` has no Linux wheels and always compiles from source — that's expected, and it needs the cairo/pango headers above.

## Configure

```bash
cp .env.example .env
```

Set **one** provider key:

```bash
ANTHROPIC_API_KEY=sk-ant-...     # or OPENAI_API_KEY=sk-...
USE_LOCAL_STORAGE=true
```

Whichever provider has a key is used automatically — you don't need to name a model per request. If both are set, OpenAI wins unless you pass `model` or set `DEFAULT_MODEL`. Leave unused keys blank rather than filling in a placeholder.

## Run

```bash
.venv/bin/python run.py
```

Serves on `http://127.0.0.1:8080`. Run it from the repo root — `.env` loading and the `api/public` output path both resolve relative to it.

> Use the root `run.py`, not `api/run.py`. The latter fails with `ModuleNotFoundError: No module named 'api'` because it puts `api/` rather than the repo root on `sys.path`.

## Usage

```bash
curl -X POST http://127.0.0.1:8080/v1/video/rendering \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain the Pythagorean theorem", "quality": "low"}'
```

```json
{
  "message": "Video generation completed",
  "video_url": "http://127.0.0.1:8080/public/video-<uuid>-None-None.mp4"
}
```

**Start with `"quality": "low"`** — it renders in well under a minute. The default `high` (1080p60) takes several minutes and is easy to mistake for a hang.

### Request fields

| Field | Default | Notes |
|---|---|---|
| `prompt` | — | The topic to explain |
| `model` | auto | `claude-opus-5`, `claude-sonnet-5`, `gpt-4o`, … Auto-selected from the configured key |
| `domain` | `default` | Any filename in `config/domains/` |
| `quality` | `high` | `low` (480p) · `medium` (720p) · `high` (1080p) · `ultra` (4K) |
| `aspect_ratio` | `16:9` | `16:9` · `9:16` · `1:1` |
| `voiceover` | `true` | Set `false` for a silent render |
| `stream` | `false` | Stream NDJSON progress instead of one blocking response |
| `project_name`, `iteration`, `user_id` | — | Used to build the output filename |

### Streaming

```bash
curl -X POST http://127.0.0.1:8080/v1/video/rendering \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain entropy", "quality": "low", "stream": true}'
```

```
{"animationIndex": 0, "percentage": 0}
{"animationIndex": 0, "percentage": 47}
{"message": "Video generation completed", "video_url": "..."}
```

### Cached GET

Hashes the prompt and reuses an existing render, so repeats cost nothing:

```bash
curl "http://127.0.0.1:8080/v1/video/play?prompt=Explain+entropy&quality=low"
```

### Domain scripts

```bash
./generative-physics.sh   "Explain Newton's second law"
./generative-chemistry.sh "Show molecular orbital theory"
./generative-default.sh   "Visualize sorting algorithms"
```

## Narration

Narrated scenes extend `VoiceoverScene` and wrap each animation so the visuals last as long as the speech:

```python
with self.voiceover(text="Here is a blue circle.") as tracker:
    self.play(Create(c), run_time=tracker.duration)
```

gTTS calls Google Translate's TTS endpoint, so **rendering a narrated video needs network access** — no account or key. Pass `"voiceover": false` for a silent render. For higher-quality voices, `manim-voiceover` also supports ElevenLabs, Azure, and OpenAI TTS; each needs its own credentials.

## Custom domains

Add a JSON file to `config/domains/` and pass its name as `domain`:

```json
{
  "domain": "Your Domain",
  "system_prompt": "You are an expert in...",
  "target_template": "Create an educational video about...",
  "translation_rule": "Translate to standard terminology",
  "example_topics": ["topic one", "topic two"]
}
```

An unknown `domain` falls back to `default.json`. See [DOMAINS.md](DOMAINS.md).

## API endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/video/rendering` | Generate and render a video from a prompt |
| `GET /v1/video/play` | Same, cached by prompt hash |
| `POST /v1/video/exporting` | Concatenate several rendered scenes with ffmpeg |
| `POST /v1/code/generation` | Return Manim code without rendering |
| `POST /v1/chat/generation` | Interactive chat mode with image input |
| `GET /public/<name>.mp4` | Serve a rendered video (local storage mode) |

## Storage

Local by default: videos are written to `api/public/` and served at `/public/<name>.mp4`.

For cloud storage, set `USE_LOCAL_STORAGE=false` and install the SDK you need — both are imported lazily and are commented out in `api/requirements.txt`:

```bash
# Google Cloud Storage
uv pip install --python .venv/bin/python google-cloud-storage
# then set GOOGLE_CLOUD_FILE and GOOGLE_BUCKET_NAME

# Azure Blob Storage
uv pip install --python .venv/bin/python azure-storage-blob
# then set AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER_NAME
```

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

No network and no API credits — the LLM is stubbed throughout. Tests that shell out to Manim (including one that renders a narrated clip and asserts the audio track isn't silent) skip automatically when Manim isn't installed.

## Docker

```bash
./docker_deploy.sh                              # build and push
./service.sh                                    # pull and run
DOCKER_IMAGE_NAME=my-org/manim ./docker_deploy.sh
```

The `Dockerfile` targets `python:3.9-slim`, which differs from the 3.11 used locally.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `502` with a credentials message | No usable provider key. A placeholder shorter than 20 characters is ignored on purpose |
| `500` with a `log` field | The generated Manim code failed to render — the full traceback is in `log`, usually a LaTeX error |
| Render seems to hang | `quality` defaults to `high` (1080p60). Use `"quality": "low"` |
| Narrated render fails with a network error | gTTS can't reach Google. Retry, or pass `"voiceover": false` |
| `ModuleNotFoundError: No module named 'api'` | You ran `api/run.py`; use the root `run.py` |
| `pkg_resources` ImportError | setuptools 81+ removed it; `api/requirements.txt` pins `setuptools<81` |
| Pillow fails to build on install | The venv isn't Python 3.11 |

## Project structure

```
generative-manim/
├── run.py                       # entry point
├── api/
│   ├── __init__.py              # create_app()
│   ├── requirements.txt
│   ├── public/                  # rendered videos (gitignored)
│   ├── prompts/manimDocs.py
│   └── routes/
│       ├── video_rendering.py   # generation + render + publish
│       ├── code_generation.py
│       └── chat_generation.py
├── config/domains/              # default.json, physics.json, chemistry.json
├── tests/
├── generative-*.sh              # domain helper scripts
├── docker_deploy.sh, service.sh, Dockerfile
└── DOMAINS.md
```

## License

Intended to be MIT, but there is no `LICENSE` file in the repo yet — add one before
publishing, since without it the code is technically unlicensed.
