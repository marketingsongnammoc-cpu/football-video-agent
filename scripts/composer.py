"""
composer.py — Ghép video MP4 từ bg + overlay + audio mỗi scene.

Dùng ffmpeg subprocess trực tiếp (zoompan filter) thay vì MoviePy per-frame Python,
nhanh hơn 10-20x so với phương pháp cũ.

KEN BURNS MOTION (ngẫu nhiên mỗi scene):
- zoom_in   : 1.0x → 1.15x
- zoom_out  : 1.15x → 1.0x
- pan_left  : pan từ phải sang trái (zoom cố định 1.1x)
- pan_right : pan từ trái sang phải (zoom cố định 1.1x)
"""

from __future__ import annotations
from pathlib import Path
import json
import random
import shutil
import subprocess
import tempfile
from typing import Literal


FRAME_W, FRAME_H = 720, 1280
FPS = 30
SILENCE_AFTER = 0.5  # giây im lặng sau mỗi scene

MotionKind = Literal["zoom_in", "zoom_out", "pan_left", "pan_right"]
ALL_MOTIONS: list[MotionKind] = ["zoom_in", "zoom_out", "pan_left", "pan_right"]


# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────

def _get_audio_duration(audio_path: Path) -> float:
    """ffprobe để lấy duration audio."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    for stream in json.loads(result.stdout).get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream["duration"])
    raise ValueError(f"Không lấy được duration: {audio_path}")


def _zoompan_expr(motion: MotionKind, total_frames: int) -> str:
    """
    Sinh ffmpeg zoompan filter string.

    bg image: 936×1040, output photo zone: 720×800.
    Dùng smoothstep easing (p²·(3-2p)) để motion mượt — không giật đầu/cuối.
    """
    N = max(total_frames, 1)
    OUT_W, OUT_H = 720, 1280   # full frame — không cần pad

    # Smoothstep easing: p = on/N, eased = p²(3-2p)
    p   = f"(on/{N})"
    e   = f"({p}*{p}*(3-2*{p}))"  # 0→1 mượt

    center_x = f"(iw-({OUT_W}/zoom))/2"
    center_y = f"(ih-({OUT_H}/zoom))/2"

    if motion == "zoom_in":
        z = f"1+0.12*{e}"
        x, y = center_x, center_y
    elif motion == "zoom_out":
        z = f"1.12-0.12*{e}"
        x, y = center_x, center_y
    elif motion == "pan_left":
        z = "1.08"
        x = f"(iw-({OUT_W}/zoom))/2+60/zoom*(2*{e}-1)"
        y = center_y
    elif motion == "pan_right":
        z = "1.08"
        x = f"(iw-({OUT_W}/zoom))/2+60/zoom*(1-2*{e})"
        y = center_y
    else:
        raise ValueError(f"Unknown motion: {motion}")

    return (
        f"zoompan=z='{z}':x='{x}':y='{y}'"
        f":d={N}:s={OUT_W}x{OUT_H}:fps={FPS}"
    )


# ───────────────────────────────────────────────────────────
# Per-scene render
# ───────────────────────────────────────────────────────────

def _render_scene(bg_path: Path, overlay_path: Path, audio_path: Path,
                  output_path: Path, motion: MotionKind) -> float:
    """
    Render 1 scene thành MP4 bằng ffmpeg.
    Trả về total duration (giây).
    """
    audio_dur = _get_audio_duration(audio_path)
    total_dur = audio_dur + SILENCE_AFTER
    total_frames = int(total_dur * FPS)

    zoompan = _zoompan_expr(motion, total_frames)

    # filter_complex:
    # [0] bg jpg (936×1664) → zoompan full frame (720×1280) — không cần pad
    # [1] overlay PNG (RGBA 720×1280) → composite lên toàn frame
    # [2] audio → apad để thêm im lặng đến total_dur
    filter_complex = (
        f"[0:v]{zoompan}[kbg];"
        f"[1:v]format=rgba[ov];"
        f"[kbg][ov]overlay=0:0[v];"
        f"[2:a]apad=whole_dur={total_dur}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(bg_path),
        "-i", str(overlay_path),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-t", str(total_dur),
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg scene error:\n{result.stderr[-2000:]}")
    return total_dur


# ───────────────────────────────────────────────────────────
# Concatenate
# ───────────────────────────────────────────────────────────

def _concat_scenes(scene_files: list[Path], output_path: Path) -> None:
    """Nối các scene MP4 bằng ffmpeg concat demuxer (không re-encode)."""
    list_file = Path(tempfile.mktemp(suffix=".txt"))
    try:
        list_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in scene_files),
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat error:\n{result.stderr[-2000:]}")
    finally:
        list_file.unlink(missing_ok=True)


# ───────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────

def compose_video(scenes: list[dict], video_folder: Path, output_path: Path,
                  seed: int | None = None) -> dict:
    """
    Ghép video MP4 từ folder dự án.

    Args:
        scenes: list scene dict (mỗi scene có id "01", "02", ...)
        video_folder: folder chứa frames/ và audio/
        output_path: đường dẫn file mp4 đầu ra
        seed: random seed cho motion (None = random thật)

    Returns: {duration, scenes_meta, output}
    """
    if seed is not None:
        random.seed(seed)

    frames_dir = video_folder / "frames"
    audio_dir  = video_folder / "audio"
    tmp_dir    = video_folder / "_tmp_scenes"
    tmp_dir.mkdir(exist_ok=True)

    # Chọn motion đa dạng (không trùng 2 scene liên tiếp)
    motions: list[MotionKind] = []
    if len(scenes) <= 4:
        motions = random.sample(ALL_MOTIONS, k=len(scenes))
    else:
        prev = None
        for _ in scenes:
            choices = [m for m in ALL_MOTIONS if m != prev]
            m = random.choice(choices)
            motions.append(m)
            prev = m

    scene_files: list[Path] = []
    scenes_meta: list[dict] = []
    total_duration = 0.0

    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"{idx+1:02d}")
        bg_path      = frames_dir / f"bg_{scene_id}.jpg"
        overlay_path = frames_dir / f"overlay_{scene_id}.png"
        audio_path   = audio_dir  / f"scene_{scene_id}.mp3"

        for p in (bg_path, overlay_path, audio_path):
            if not p.exists():
                raise FileNotFoundError(f"Thiếu file: {p}")

        motion = motions[idx]
        print(f"  scene {scene_id}: motion={motion}", flush=True)

        scene_out = tmp_dir / f"scene_{scene_id}.mp4"
        dur = _render_scene(bg_path, overlay_path, audio_path, scene_out, motion)

        scene_files.append(scene_out)
        scenes_meta.append({"id": scene_id, "motion": motion, "duration": dur})
        total_duration += dur

    print(f"  [composer] Ghép {len(scene_files)} scenes...", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _concat_scenes(scene_files, output_path)

    shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "duration": total_duration,
        "scenes_meta": scenes_meta,
        "output": str(output_path),
    }


if __name__ == "__main__":
    print("composer.py — module để compose video. Dùng test_composer.py để test.")
