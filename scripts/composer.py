"""
composer.py — Ghép video MP4 từ bg + overlay + audio mỗi scene.

KEN BURNS: dùng PIL affine transform per-frame (subpixel chính xác).

Tại sao không dùng ffmpeg zoompan/scale+crop:
  - ffmpeg buộc phải làm tròn tọa độ về integer → nhảy ±1px/frame → giật
  - PIL Image.transform(AFFINE) xử lý float coordinates + BICUBIC interpolation
    → subpixel smooth, không có artifact

Pipeline mỗi scene:
  1. PIL: render từng frame (bg affine + overlay composite) → JPEG sequence
  2. ffmpeg: encode JPEG sequence + audio → scene.mp4
  3. ffmpeg concat: ghép tất cả scenes → video.mp4
"""

from __future__ import annotations
from pathlib import Path
import json
import random
import shutil
import subprocess
import tempfile
from typing import Literal

from PIL import Image

FRAME_W, FRAME_H = 720, 1280
FPS = 30
SILENCE_AFTER = 0.5       # giây im lặng sau mỗi scene
ZOOM_RANGE    = 0.10      # zoom 10% (ít hơn cũ 12%, smoother)
PAN_OFFSET    = 65        # pixels pan left/right trong source space

MotionKind = Literal["zoom_in", "zoom_out", "pan_left", "pan_right"]
ALL_MOTIONS: list[MotionKind] = ["zoom_in", "zoom_out", "pan_left", "pan_right"]


# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────

def _get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    for stream in json.loads(result.stdout).get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream["duration"])
    raise ValueError(f"Không lấy được duration: {audio_path}")


def _smoothstep(t: float) -> float:
    """Smoothstep easing: 0→1, không giật đầu/cuối."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _compute_affine(motion: MotionKind, e: float, bg_w: int, bg_h: int) -> tuple:
    """
    Tính affine matrix cho PIL.Image.transform.

    PIL AFFINE: output(x,y) ← input(a*x + b*y + c, d*x + e_*y + f)
    Với zoom + pan thuần (không xoay): b=0, d=0
      → input_x = (1/zoom)*out_x + offset_x
      → input_y = (1/zoom)*out_y + offset_y

    offset_x/y là tọa độ góc trên-trái của vùng crop trong source.
    """
    if motion == "zoom_in":
        zoom = 1.0 + ZOOM_RANGE * e
    elif motion == "zoom_out":
        zoom = (1.0 + ZOOM_RANGE) - ZOOM_RANGE * e
    else:  # pan
        zoom = 1.0 + ZOOM_RANGE * 0.8   # fixed ~1.08x

    inv_z = 1.0 / zoom

    # Vùng cần crop trong source (float)
    crop_w = FRAME_W * inv_z
    crop_h = FRAME_H * inv_z

    # Offset pan ngang
    if motion == "pan_left":
        pan_x = PAN_OFFSET * (1 - 2 * e)    # +offset → -offset
    elif motion == "pan_right":
        pan_x = PAN_OFFSET * (2 * e - 1)    # -offset → +offset
    else:
        pan_x = 0.0

    offset_x = (bg_w - crop_w) / 2.0 + pan_x
    offset_y = (bg_h - crop_h) / 2.0

    # Clamp để không vượt ra ngoài ảnh gốc
    offset_x = max(0.0, min(offset_x, bg_w - crop_w))
    offset_y = max(0.0, min(offset_y, bg_h - crop_h))

    # PIL affine tuple: (a, b, c, d, e_, f) — single-channel per axis
    return (inv_z, 0.0, offset_x, 0.0, inv_z, offset_y)


# ───────────────────────────────────────────────────────────
# Per-scene render: PIL frames → ffmpeg encode
# ───────────────────────────────────────────────────────────

def _render_scene(bg_path: Path, overlay_path: Path, audio_path: Path,
                  output_path: Path, motion: MotionKind) -> float:
    """
    Render 1 scene:
      1. PIL affine per-frame → JPEG sequence (subpixel smooth)
      2. ffmpeg encode sequence + audio → MP4
    Trả về total duration (giây).
    """
    audio_dur  = _get_audio_duration(audio_path)
    total_dur  = audio_dur + SILENCE_AFTER
    n_frames   = int(total_dur * FPS)

    bg      = Image.open(bg_path).convert("RGB")
    overlay = Image.open(overlay_path).convert("RGBA")
    bg_w, bg_h = bg.size

    tmp_dir = output_path.parent / f"_frames_{output_path.stem}"
    tmp_dir.mkdir(exist_ok=True)

    try:
        # ── Render frames ──
        for n in range(n_frames):
            t = n / max(n_frames - 1, 1)          # 0.0 → 1.0
            e = _smoothstep(t)
            affine = _compute_affine(motion, e, bg_w, bg_h)

            # Subpixel-accurate crop + zoom qua PIL affine
            frame = bg.transform(
                (FRAME_W, FRAME_H),
                Image.Transform.AFFINE,
                affine,
                resample=Image.Resampling.BICUBIC,
            )

            # Composite overlay (text, gradient, tag pill...)
            frame_rgba = frame.convert("RGBA")
            frame_rgba.alpha_composite(overlay)

            frame_rgba.convert("RGB").save(
                tmp_dir / f"f{n:05d}.jpg", "JPEG", quality=94,
            )

        # ── ffmpeg encode: JPEG sequence + audio → MP4 ──
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(tmp_dir / "f%05d.jpg"),
            "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-t", f"{total_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100",
            "-shortest",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg encode error:\n{result.stderr[-2000:]}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

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
        scene_id     = scene.get("id", f"{idx+1:02d}")
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
