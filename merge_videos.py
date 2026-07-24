#!/usr/bin/env python3
"""
Merge 5 method videos per scene into a single side-by-side MP4.

For each scene folder, the 5 method videos are arranged horizontally
in a deterministic-random order with white gaps between them.
The order mapping is written to video_order.js for the HTML to consume.

Usage:
    python merge_videos.py              # process all scene folders
    python merge_videos.py 03           # process only scene 03
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys

METHODS = ["ours", "tcdiff", "tcdiffpp", "tcdiffstar", "edge"]
SCENES = ["01", "02", "03", "04"]
GAP = 20  # white gap in pixels between videos
GLOBAL_SEED = 20260724

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def stable_seed(scene_name: str) -> int:
    h = hashlib.sha256(f"{GLOBAL_SEED}:{scene_name}".encode()).hexdigest()
    return int(h[:12], 16)


def get_video_info(path: str):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    width = height = 0
    has_audio = False
    for s in info.get("streams", []):
        if s["codec_type"] == "video":
            width = int(s["width"])
            height = int(s["height"])
        elif s["codec_type"] == "audio":
            has_audio = True
    return width, height, has_audio


def merge_scene(scene_folder: str) -> list[str] | None:
    folder_path = os.path.join(BASE_DIR, scene_folder)

    video_paths = {}
    for m in METHODS:
        p = os.path.join(folder_path, f"{m}.mp4")
        if not os.path.isfile(p):
            print(f"  ⏭  Skipping scene {scene_folder}: {m}.mp4 not found")
            return None
        video_paths[m] = p

    rng = random.Random(stable_seed(scene_folder))
    shuffled_methods = list(METHODS)
    rng.shuffle(shuffled_methods)

    ordered_paths = [video_paths[m] for m in shuffled_methods]

    audio_input_idx = None
    target_h = 0
    for i, path in enumerate(ordered_paths):
        w, h, has_audio = get_video_info(path)
        if target_h == 0:
            target_h = h
        if has_audio and audio_input_idx is None:
            audio_input_idx = i

    inputs = []
    for path in ordered_paths:
        inputs.extend(["-i", path])

    n = len(ordered_paths)
    filter_parts = []
    for i in range(n):
        if i < n - 1:
            filter_parts.append(
                f"[{i}:v]scale=-2:{target_h}:flags=lanczos,setsar=1,"
                f"pad=iw+{GAP}:ih:0:0:white[v{i}]"
            )
        else:
            filter_parts.append(
                f"[{i}:v]scale=-2:{target_h}:flags=lanczos,setsar=1[v{i}]"
            )

    inputs_str = "".join(f"[v{i}]" for i in range(n))
    filter_parts.append(f"{inputs_str}hstack=inputs={n}[out]")
    filter_complex = ";".join(filter_parts)

    output_path = os.path.join(folder_path, "merged.mp4")

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
    ]

    if audio_input_idx is not None:
        cmd.extend(["-map", f"{audio_input_idx}:a"])

    cmd.extend([
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ])

    print(f"  🔨 Merging scene {scene_folder}: {' → '.join(shuffled_methods)}")
    subprocess.run(cmd, check=True)
    print(f"  ✅ Written {output_path}")

    return shuffled_methods


def write_order_js(order_map: dict):
    path = os.path.join(BASE_DIR, "video_order.js")
    js = "const VIDEO_ORDER = " + json.dumps(order_map, indent=2) + ";\n"
    with open(path, "w") as f:
        f.write(js)
    print(f"\n📄 Written {path}")


def main():
    target_scenes = sys.argv[1:] if len(sys.argv) > 1 else SCENES

    existing_order = {}
    order_js_path = os.path.join(BASE_DIR, "video_order.js")
    if os.path.isfile(order_js_path):
        try:
            with open(order_js_path) as f:
                content = f.read()
            json_str = content.replace("const VIDEO_ORDER = ", "").rstrip(";\n")
            existing_order = json.loads(json_str)
        except Exception:
            pass

    order_map = dict(existing_order)

    for scene in target_scenes:
        if scene not in SCENES:
            print(f"  ⚠️  Unknown scene: {scene}")
            continue
        print(f"\nProcessing scene {scene}...")
        result = merge_scene(scene)
        if result is not None:
            order_map[scene] = result

    if order_map:
        write_order_js(order_map)
    else:
        print("\nNo scenes were processed.")


if __name__ == "__main__":
    main()
