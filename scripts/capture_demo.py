#!/usr/bin/env python
"""Render demo videos offline and write scrubbed artifacts for the portfolio.

    python scripts/capture_demo.py --out /home/ryan/portfolio/public/demos/manim
    python scripts/capture_demo.py --only bond-price-yield --quality low

Per prompt it writes:  prompt.txt  scene.py  run.json  meta.json  out.mp4
Every text artifact is scrubbed and then re-checked before it touches disk.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

# This script never builds the Flask app, so nothing else loads .env for it.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from api.pipeline.events import RunRecorder  # noqa: E402
from api.pipeline.run import run_pipeline  # noqa: E402
from api.pipeline.scrub import assert_clean, scrub_obj, scrub_text  # noqa: E402
from api.routes.video_rendering import (  # noqa: E402
    generate_llm_result,
    iter_render_scene,
)

# GitHub warns at 50MB and hard-rejects at 100MB; these ride in the repo.
MAX_MP4_BYTES = 10 * 1024 * 1024

PROMPTS = [
    {
        "slug": "bond-price-yield",
        "prompt": "Show how a bond's price moves inversely with its yield",
        "aspect_ratio": "16:9",
    },
    {
        "slug": "fourier-square-wave",
        "prompt": "Visualize a Fourier series converging to a square wave",
        "aspect_ratio": "16:9",
    },
    {
        "slug": "pythagorean-rearrangement",
        "prompt": "Prove the Pythagorean theorem by rearranging four triangles",
        "aspect_ratio": "9:16",
    },
    {
        "slug": "black-scholes-derivation",
        "prompt": "Derive the Black-Scholes PDE step by step",
        "aspect_ratio": "16:9",
    },
    {
        "slug": "central-limit-dice",
        "prompt": "Show the central limit theorem by summing dice rolls",
        "aspect_ratio": "16:9",
    },
]


def probe(path: Path) -> dict:
    """Read resolution, duration, frame count, and audio presence from the MP4."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,nb_frames",
         "-show_entries", "format=duration,size", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return {
        "width": video.get("width"),
        "height": video.get("height"),
        "frames": int(video["nb_frames"]) if video.get("nb_frames") else None,
        "duration_s": round(float(data.get("format", {}).get("duration", 0)), 2),
        "size_bytes": int(data.get("format", {}).get("size", 0)),
        "has_audio": has_audio,
    }


def finalize_mp4(src: Path, dest: Path) -> dict:
    """Move the video into place with faststart, shrinking it if oversized."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src),
         "-c", "copy", "-movflags", "+faststart", str(dest)],
        check=True,
    )
    info = probe(dest)
    if info["size_bytes"] > MAX_MP4_BYTES:
        print(f"    {info['size_bytes'] / 1e6:.1f}MB exceeds cap, re-encoding")
        shrunk = dest.with_suffix(".shrunk.mp4")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(dest),
             "-c:v", "libx264", "-crf", "30", "-preset", "slow",
             "-c:a", "aac", "-b:a", "64k",
             "-movflags", "+faststart", str(shrunk)],
            check=True,
        )
        shrunk.replace(dest)
        info = probe(dest)
    return info


def write_text(path: Path, text: str) -> None:
    cleaned = scrub_text(text)
    assert_clean(cleaned, path.name)
    path.write_text(cleaned, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    cleaned = scrub_obj(obj)
    text = json.dumps(cleaned, indent=2)
    assert_clean(text, path.name)
    path.write_text(text, encoding="utf-8")


def capture_one(spec: dict, out_root: Path, quality: str, model: str | None) -> bool:
    slug = spec["slug"]
    dest = out_root / slug
    dest.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {slug} ===\n    {spec['prompt']}")

    workdir = tempfile.mkdtemp(prefix="genmanim-capture-")
    recorder = RunRecorder(slug)
    try:
        result = None
        for event in run_pipeline(
            spec["prompt"], slug,
            generate=generate_llm_result,
            render=iter_render_scene,
            workdir=workdir,
            model=model,
            quality=quality,
            aspect_ratio=spec["aspect_ratio"],
            voiceover=True,
            recorder=recorder,
        ):
            if "result" in event:
                result = event["result"]
            elif "msg" in event:
                print(f"    {event.get('stage', '')}: {event['msg']}")

        info = finalize_mp4(Path(result.video_path), dest / "out.mp4")
        result.extra_meta = {
            "aspect_ratio": spec["aspect_ratio"],
            "quality": quality,
            "resolution": f"{info['width']}x{info['height']}",
            "duration_s": info["duration_s"],
            "frames": info["frames"],
            "size_bytes": info["size_bytes"],
            "has_audio": info["has_audio"],
            "voiceover": True,
        }

        write_text(dest / "prompt.txt", spec["prompt"] + "\n")
        write_text(dest / "scene.py", result.code)
        write_json(dest / "run.json", recorder.to_run_json())
        write_json(dest / "meta.json", result.to_meta())

        print(f"    OK {info['width']}x{info['height']} {info['duration_s']}s "
              f"{info['size_bytes'] / 1e6:.1f}MB audio={info['has_audio']} "
              f"attempts={result.attempts}")
        return True

    except Exception as e:
        print(f"    FAILED: {e}")
        # Keep the partial run log -- a captured failure is worth showing.
        write_json(dest / "run.json", recorder.to_run_json())
        write_json(dest / "meta.json", {"slug": slug, "error": str(e)[:500]})
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/home/ryan/portfolio/public/demos/manim")
    parser.add_argument("--quality", default="medium",
                        choices=["low", "medium", "high", "ultra"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--only", action="append",
                        help="slug to capture; repeatable. Defaults to all.")
    args = parser.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    specs = PROMPTS
    if args.only:
        specs = [p for p in PROMPTS if p["slug"] in args.only]
        missing = set(args.only) - {p["slug"] for p in specs}
        if missing:
            print(f"unknown slug(s): {', '.join(sorted(missing))}")
            return 2

    print(f"capturing {len(specs)} prompt(s) at quality={args.quality} -> {out_root}")
    ok = sum(capture_one(s, out_root, args.quality, args.model) for s in specs)
    write_index(out_root)
    print(f"\n{ok}/{len(specs)} succeeded")
    return 0 if ok == len(specs) else 1


def write_index(out_root: Path) -> None:
    """Write index.json listing every captured demo.

    The site is static with no backend, so the page needs a manifest on disk to
    know which demos exist.
    """
    # Ordered by PROMPTS, not alphabetically: the first entry is what the page
    # shows by default, so the running order is an editorial choice.
    order = {spec["slug"]: i for i, spec in enumerate(PROMPTS)}
    meta_paths = sorted(
        out_root.glob("*/meta.json"),
        key=lambda p: (order.get(p.parent.name, len(order)), p.parent.name),
    )

    entries = []
    for meta_path in meta_paths:
        meta = json.loads(meta_path.read_text())
        prompt_path = meta_path.parent / "prompt.txt"
        entries.append({
            "slug": meta_path.parent.name,
            "prompt": prompt_path.read_text().strip() if prompt_path.exists() else "",
            "aspect_ratio": meta.get("aspect_ratio", "16:9"),
            "duration_s": meta.get("duration_s"),
            "model": meta.get("model"),
            "cost_cents": meta.get("cost_cents"),
            "attempts": meta.get("attempts"),
            "total_ms": meta.get("total_ms"),
            "has_video": (meta_path.parent / "out.mp4").exists(),
            "error": meta.get("error"),
        })
    write_json(out_root / "index.json", entries)
    print(f"wrote index.json with {len(entries)} entries")


if __name__ == "__main__":
    raise SystemExit(main())
