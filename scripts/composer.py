"""
composer.py — Ghép video từ static template frame + audio.

Thay vì PIL per-frame render (3 phút), dùng ffmpeg:
  - Input: composite PNG (1080×1920) + audio MP3
  - Motion: zoom RẤT NHẸ 100%→103% (không làm lệch template)
  - Output: MP4 per scene → concat → video cuối

Theo quy trình template THỂ THAO 247:
  - KHÔNG Ken Burns phức tạp (template là tài sản cố định)
  - Chỉ zoom tối đa 3%, fade in/out 0.3s
  - Không thêm hiệu ứng lòe loẹt
"""

from __future__ import annotations
from pathlib import Path
import json
import random
import shutil
import subprocess
import tempfile
from typing import Literal

CANVAS_W, CANVAS_H = 1080, 1920
FPS          = 30
SILENCE_AFTER = 0.4   # giây im lặng cuối scene
MAX_ZOOM     = 1.03   # zoom tối đa 3% (đủ cảm giác motion, không lệch template)

MotionKind = Literal["zoom_in", "zoom_out", "pan_left", "pan_right"]
ALL_MOTIONS: list[MotionKind] = ["zoom_in", "zoom_out", "pan_left", "pan_right"]


def _get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    for stream in json.loads(result.stdout).get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream["duration"])
    raise ValueError(f"Không lấy được duration: {audio_path}")


def _render_scene(frame_path: Path, audio_path: Path,
                  output_path: Path, motion: MotionKind,
                  img_raw_path: Path | None = None) -> float:
    """Render 1 scene → MP4.
    Nếu img_raw_path tồn tại: chỉ zoom ảnh, template/text đứng yên.
    Ngược lại: zoom cả frame (fallback).
    """
    audio_dur = _get_audio_duration(audio_path)
    total_dur = audio_dur + SILENCE_AFTER
    n_frames  = int(total_dur * FPS)
    fade_d    = 0.3

    z_in  = motion in ("zoom_in", "pan_right")
    z_expr = f"1+{MAX_ZOOM-1}*on/{n_frames}" if z_in else f"{MAX_ZOOM}-{MAX_ZOOM-1}*on/{n_frames}"

    if img_raw_path and img_raw_path.exists():
        # ── Chế độ 2 lớp: zoom ảnh riêng, overlay template tĩnh ──
        sidecar = img_raw_path.parent / img_raw_path.name.replace("img_raw_", "img_slot_").replace(".png", ".json")
        if sidecar.exists():
            _slot = json.loads(sidecar.read_text(encoding="utf-8"))
            iw, ih, ix, iy = _slot["w"], _slot["h"], _slot["x"], _slot["y"]
        else:
            from scripts.scene_renderer import _TN_IMG  # type: ignore
            iw, ih = _TN_IMG["w"], _TN_IMG["h"]
            ix, iy = _TN_IMG["x"], _TN_IMG["y"]
        vf = (
            f"[0:v]zoompan=z='{z_expr}':d={n_frames}:s={iw}x{ih}:fps={FPS}[zoomed];"
            f"[zoomed]pad={CANVAS_W}:{CANVAS_H}:{ix}:{iy}:black[padded];"
            f"[padded][1:v]overlay=0:0:format=auto,"
            f"fade=t=in:st=0:d={fade_d},"
            f"fade=t=out:st={total_dur-fade_d:.3f}:d={fade_d}[v];"
            f"[2:a]apad=whole_dur={total_dur}[a]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(img_raw_path),
            "-loop", "1", "-framerate", str(FPS), "-i", str(frame_path),
            "-i", str(audio_path),
            "-filter_complex", vf,
            "-map", "[v]", "-map", "[a]",
            "-t", f"{total_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100",
            str(output_path),
        ]
    else:
        # ── Chế độ 1 lớp: zoom cả frame ──
        vf = (
            f"zoompan=z='{z_expr}':d={n_frames}:s={CANVAS_W}x{CANVAS_H}:fps={FPS},"
            f"fade=t=in:st=0:d={fade_d},"
            f"fade=t=out:st={total_dur-fade_d:.3f}:d={fade_d}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(frame_path),
            "-i", str(audio_path),
            "-filter_complex",
                f"[0:v]{vf}[v];"
                f"[1:a]apad=whole_dur={total_dur}[a]",
            "-map", "[v]", "-map", "[a]",
            "-t", f"{total_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg scene error:\n{result.stderr[-2000:]}")
    return total_dur


def _render_end_card(frame_path: Path, output_path: Path,
                     duration: float = 3.0) -> None:
    """Render end card tĩnh (silence) duration giây."""
    fade_d = 0.3
    vf = (
        f"fade=t=in:st=0:d={fade_d},"
        f"fade=t=out:st={duration-fade_d:.1f}:d={fade_d}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(frame_path),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", f"{duration:.1f}",
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg end card error:\n{result.stderr[-2000:]}")


def _concat_scenes(scene_files: list[Path], output_path: Path) -> None:
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


def compose_video(scenes: list[dict], video_folder: Path, output_path: Path,
                  seed: int | None = None) -> dict:
    if seed is not None:
        random.seed(seed)

    frames_dir = video_folder / "frames"
    audio_dir  = video_folder / "audio"
    tmp_dir    = video_folder / "_tmp_scenes"
    tmp_dir.mkdir(exist_ok=True)

    # Chọn motion đa dạng (không trùng liên tiếp)
    motions: list[MotionKind] = []
    if len(scenes) <= 4:
        motions = random.sample(ALL_MOTIONS, k=len(scenes))
    else:
        prev = None
        for _ in scenes:
            choices = [m for m in ALL_MOTIONS if m != prev]
            m = random.choice(choices)
            motions.append(m); prev = m

    scene_files: list[Path] = []
    scenes_meta: list[dict] = []
    total_duration = 0.0

    for idx, scene in enumerate(scenes):
        scene_id     = scene.get("id", f"{idx+1:02d}")
        frame_path   = frames_dir / f"overlay_{scene_id}.png"
        img_raw_path = frames_dir / f"img_raw_{scene_id}.png"
        audio_path   = audio_dir  / f"scene_{scene_id}.mp3"

        for p in (frame_path, audio_path):
            if not p.exists():
                raise FileNotFoundError(f"Thiếu file: {p}")

        motion    = motions[idx]
        has_raw   = img_raw_path.exists()
        print(f"  scene {scene_id}: motion={motion}  zoom={'image-only' if has_raw else 'full-frame'}", flush=True)

        scene_out = tmp_dir / f"scene_{scene_id}.mp4"
        dur = _render_scene(frame_path, audio_path, scene_out, motion,
                            img_raw_path=img_raw_path if has_raw else None)

        scene_files.append(scene_out)
        scenes_meta.append({"id": scene_id, "motion": motion, "duration": dur})
        total_duration += dur

    # End card 3s
    from scripts.scene_renderer import render_end_card_frame  # type: ignore
    end_card_png = frames_dir / "end_card.png"
    end_card_mp4 = tmp_dir / "scene_end.mp4"
    render_end_card_frame(end_card_png)
    _render_end_card(end_card_png, end_card_mp4, duration=3.0)
    scene_files.append(end_card_mp4)
    print(f"  end card: 3s static", flush=True)

    print(f"  [composer] Ghép {len(scene_files)} scenes + end card...", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _concat_scenes(scene_files, output_path)
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "duration": total_duration + 3.0,
        "scenes_meta": scenes_meta,
        "output": str(output_path),
    }
