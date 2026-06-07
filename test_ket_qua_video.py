#!/usr/bin/env python3
"""test_ket_qua_video.py — Tao video test ket-qua-tran-dau tu folder co san."""
import sys
import json
import subprocess
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from scene_renderer import _render_ket_qua, render_end_card_frame, _TN_IMG
from composer import _render_end_card, _concat_scenes, _get_audio_duration, MAX_ZOOM, FPS, SILENCE_AFTER, CANVAS_W, CANVAS_H

FOLDER = Path("output/2026-06-06_113005_soc-thang-doi-thu-hon-39-bac")
OUT    = FOLDER / "video_ket_qua_test.mp4"

KQ_SCENES = [
    {"id": "01", "home_team": "Indonesia",   "away_team": "Oman",        "score": "3 - 0",
     "headline": "Indonesia thang dam doi thu", "subtext": "Man trinh dien an tuong truoc 40000 khan gia"},
    {"id": "02", "home_team": "Arsenal",     "away_team": "Bournemouth", "score": "2 - 1",
     "headline": "Arsenal gianh 3 diem quy gia", "subtext": "Ban thang quyet dinh den o phut bu gio"},
    {"id": "03", "home_team": "Real Madrid", "away_team": "Barcelona",   "score": "1 - 1",
     "headline": "El Clasico chia diem kich tinh", "subtext": "Tran dau cang thang den nhung phut cuoi"},
    {"id": "04", "home_team": "Man City",    "away_team": "Chelsea",     "score": "4 - 0",
     "headline": "Man City huy diet Chelsea", "subtext": "Haaland lap hat-trick, City vao top 3"},
    {"id": "05", "home_team": "Liverpool",   "away_team": "Tottenham",   "score": "2 - 0",
     "headline": "Liverpool giu vung ngoi dau", "subtext": "Salah toa sang voi 1 ban 1 kien tao"},
]

ZOOM_DIRS = ["in", "out", "in", "out", "in"]

frames_dir = FOLDER / "frames"
tmp_dir    = FOLDER / "_tmp_kq"
frames_dir.mkdir(exist_ok=True)
tmp_dir.mkdir(exist_ok=True)

# 1. Render overlay + img_raw cho moi scene
print("Rendering ket-qua frames...")
for sc in KQ_SCENES:
    sid = sc["id"]
    img = FOLDER / "images" / f"scene_{sid}.jpg"
    ov  = frames_dir / f"overlay_{sid}.png"
    raw = frames_dir / f"img_raw_{sid}.png"
    _render_ket_qua(sc, img if img.exists() else None, ov, raw)
    print(f"  scene {sid}: {sc['home_team']} {sc['score']} {sc['away_team']}")

# 2. Compose moi scene
print("\nComposing scenes...")
scene_files = []
for i, sc in enumerate(KQ_SCENES):
    sid   = sc["id"]
    ov    = frames_dir / f"overlay_{sid}.png"
    raw   = frames_dir / f"img_raw_{sid}.png"
    audio = FOLDER / "audio" / f"scene_{sid}.mp3"
    out   = tmp_dir / f"scene_{sid}.mp4"

    audio_dur = _get_audio_duration(audio)
    total_dur = audio_dur + SILENCE_AFTER
    n_frames  = int(total_dur * FPS)
    fade_d    = 0.3
    z_in      = ZOOM_DIRS[i] == "in"
    z_expr    = f"1+{MAX_ZOOM-1}*on/{n_frames}" if z_in else f"{MAX_ZOOM}-{MAX_ZOOM-1}*on/{n_frames}"

    # Read sidecar slot info first (ket-qua has different slot than tin-nhanh)
    sidecar = frames_dir / f"img_slot_{sid}.json"
    if sidecar.exists():
        slot = json.loads(sidecar.read_text(encoding="utf-8"))
        iw, ih = slot["w"], slot["h"]
        ix, iy = slot["x"], slot["y"]
    else:
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

    if raw.exists():
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(raw),
            "-loop", "1", "-framerate", str(FPS), "-i", str(ov),
            "-i", str(audio),
            "-filter_complex", vf,
            "-map", "[v]", "-map", "[a]",
            "-t", f"{total_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100",
            str(out),
        ]
    else:
        # fallback: zoom full overlay
        vf1 = (
            f"zoompan=z='{z_expr}':d={n_frames}:s={CANVAS_W}x{CANVAS_H}:fps={FPS},"
            f"fade=t=in:st=0:d={fade_d},"
            f"fade=t=out:st={total_dur-fade_d:.3f}:d={fade_d}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(ov),
            "-i", str(audio),
            "-filter_complex", f"[0:v]{vf1}[v];[1:a]apad=whole_dur={total_dur}[a]",
            "-map", "[v]", "-map", "[a]",
            "-t", f"{total_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100",
            str(out),
        ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERROR scene {sid}:")
        print(r.stderr[-800:])
        sys.exit(1)
    else:
        print(f"  scene {sid} OK ({total_dur:.1f}s)")
    scene_files.append(out)

# 3. End card
print("\nRendering end card...")
ec_png = frames_dir / "end_card.png"
ec_mp4 = tmp_dir / "scene_end.mp4"
render_end_card_frame(ec_png)
_render_end_card(ec_png, ec_mp4, 3.0)
scene_files.append(ec_mp4)
print("  end card OK (3.0s)")

# 4. Concat
print(f"\nGhep {len(scene_files)} clips...")
_concat_scenes(scene_files, OUT)

import shutil
shutil.rmtree(tmp_dir, ignore_errors=True)
print(f"\nDone: {OUT.resolve()}")
