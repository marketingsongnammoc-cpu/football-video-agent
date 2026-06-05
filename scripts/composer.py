"""
composer.py — Ghép video MP4 từ bg + overlay + audio mỗi scene.

KEN BURNS MOTION dùng scale+crop (float expressions) thay vì zoompan:
- zoompan dùng integer pixel positions → giật 1px/frame
- scale+crop dùng floating-point → subpixel smooth, không giật

Motions:
- zoom_in   : 1.0x → 1.12x (center)
- zoom_out  : 1.12x → 1.0x (center)
- pan_left  : pan phải→trái (zoom cố định 1.08x)
- pan_right : pan trái→phải (zoom cố định 1.08x)
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


def _ken_burns_filter(motion: MotionKind, total_dur: float) -> str:
    """
    Smooth Ken Burns dùng scale+crop với float expressions (t = timestamp giây).

    Tại sao không dùng zoompan:
    - zoompan làm tròn x,y về integer → nhảy 1px/frame → rung/giật rõ
    - scale+crop: scale dùng float, crop auto-center → subpixel smooth

    Input bg: BG_W×BG_H (936×1664)
    Output: FRAME_W×FRAME_H (720×1280)
    """
    OUT_W, OUT_H = FRAME_W, FRAME_H
    D = max(total_dur, 0.1)

    # Smoothstep easing dùng t (float timestamp 0→D)
    p = f"(t/{D:.6f})"
    e = f"({p}*{p}*(3-2*{p}))"   # 0→1 smooth

    if motion == "zoom_in":
        # Scale bg lên 1.0x→1.12x, crop center cố định 720×1280
        z = f"(1+0.12*{e})"
        return (
            f"scale=w='iw*{z}':h='ih*{z}':eval=frame:flags=lanczos,"
            f"crop={OUT_W}:{OUT_H}"
        )

    elif motion == "zoom_out":
        z = f"(1.12-0.12*{e})"
        return (
            f"scale=w='iw*{z}':h='ih*{z}':eval=frame:flags=lanczos,"
            f"crop={OUT_W}:{OUT_H}"
        )

    elif motion == "pan_left":
        # Fixed 1.08x zoom, x đi từ phải (+70) sang trái (-70)
        return (
            f"scale=w='iw*1.08':h='ih*1.08':flags=lanczos,"
            f"crop={OUT_W}:{OUT_H}:"
            f"x='(iw-{OUT_W})/2+70*(1-2*{e})':y='(ih-{OUT_H})/2'"
        )

    elif motion == "pan_right":
        return (
            f"scale=w='iw*1.08':h='ih*1.08':flags=lanczos,"
            f"crop={OUT_W}:{OUT_H}:"
            f"x='(iw-{OUT_W})/2+70*(2*{e}-1)':y='(ih-{OUT_H})/2'"
        )

    else:
        raise ValueError(f"Unknown motion: {motion}")


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

    kb = _ken_burns_filter(motion, total_dur)

    # filter_complex:
    # [0] bg jpg (936×1664) → scale+crop smooth 720×1280
    # [1] overlay PNG (RGBA 720×1280) → composite
    # [2] audio → apad im lặng đến total_dur
    filter_complex = (
        f"[0:v]{kb}[kbg];"
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
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
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
