"""
Scheduled run 22:00 - 18/5/2026
Tạo 2 video tin tức bóng đá buổi tối:
  1. Chung kết Europa League 2026: Aston Villa vs SC Freiburg (20/5)
  2. Arsenal vs PSG - CL Final preview cập nhật (30/5)
Sử dụng ảnh từ các video đã render trước + audio reuse (proxy chặn TTS).
"""
import sys
import os
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path("/sessions/amazing-confident-carson/mnt/football-video-agent")
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

from scripts.script_gen import generate_script
from scripts.scene_renderer import render_all_scenes
from scripts.composer import compose_video

import unicodedata
import re


def slugify_vi(text: str, max_len: int = 50) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "d").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug[:max_len]


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_video(title_vi: str, body_vi: str,
               source_images: list, source_audio: list,
               story_key: str):
    """Tạo video từ text + ảnh nguồn + audio tái sử dụng."""
    OUTPUT_DIR = ROOT / "output"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    temp_slug = slugify_vi(title_vi)
    video_folder = OUTPUT_DIR / f"{timestamp}_{temp_slug}"
    images_dir = video_folder / "images"
    audio_dir = video_folder / "audio"
    frames_dir = video_folder / "frames"
    for d in (images_dir, audio_dir, frames_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Copy images
    from PIL import Image as PILImage
    valid_images = []
    for idx, src in enumerate(source_images, start=1):
        if len(valid_images) >= 8:
            break
        src_path = Path(src)
        if not src_path.exists():
            print(f"  ✗ Ảnh không tồn tại: {src_path}")
            continue
        dst_path = images_dir / f"scene_{idx:02d}.jpg"
        shutil.copy2(src_path, dst_path)
        try:
            with PILImage.open(dst_path) as img:
                if max(img.size) < 300:
                    dst_path.unlink()
                    continue
            valid_images.append(dst_path)
        except Exception as e:
            dst_path.unlink()
            continue

    num_scenes = len(valid_images)
    if num_scenes < 1:
        print(f"[{story_key}] Không có ảnh hợp lệ.")
        return None

    # Copy audio (tái sử dụng)
    audio_paths = [Path(a) for a in source_audio if Path(a).exists()]
    for idx, ap in enumerate(audio_paths[:num_scenes], start=1):
        dst = audio_dir / f"scene_{idx:02d}.mp3"
        shutil.copy2(ap, dst)

    print(f"\n[{story_key}] Tạo script với {num_scenes} scenes...")
    scenes = generate_script(title_vi, body_vi, num_scenes=num_scenes)
    print(f"[{story_key}] Script:")
    for s in scenes:
        print(f"  [{s['id']}] {s.get('headline', '')[:60]}")

    save_json(video_folder / "source.json", {
        "url": f"scheduled_10pm_{story_key}_{timestamp}",
        "title_vi": title_vi,
        "body_vi": body_vi,
        "source_name": "scheduled_10pm",
        "language": "vi",
        "was_translated": False,
        "num_scenes": num_scenes,
        "audio_reused": True,
    })
    save_json(video_folder / "script.json", {"scenes": scenes})

    print(f"[{story_key}] Render frames...")
    render_all_scenes(scenes, images_dir, frames_dir)

    print(f"[{story_key}] Compose video (audio reuse)...")
    output_mp4 = video_folder / "video.mp4"
    _orig_dir = os.getcwd()
    os.chdir(str(video_folder))
    result = compose_video(scenes, video_folder, output_mp4)
    os.chdir(_orig_dir)
    print(f"\n✓ [{story_key}] HOÀN THÀNH: {output_mp4}")
    print(f"  Duration: {result['duration']:.1f}s, {num_scenes} scenes")
    return output_mp4


# ─────── TIN 1: CHUNG KẾT EUROPA LEAGUE 2026 ───────
title_1 = "Chung kết Europa League 2026: Aston Villa quyết đấu Freiburg tại Istanbul"
body_1 = """Aston Villa và SC Freiburg sẽ tranh chức vô địch UEFA Europa League 2026 vào ngày 20/5 tại sân Beşiktaş Park, Istanbul, Thổ Nhĩ Kỳ. Đây là trận chung kết lịch sử với nhiều điểm đáng chú ý.

Đây là lần đầu tiên Freiburg - đội bóng đến từ Bundesliga - bước vào một trận chung kết châu Âu trong lịch sử tồn tại của CLB. Trong khi đó, Aston Villa lần đầu tiên có mặt ở một trận chung kết UEFA kể từ khi vô địch Cúp C1 năm 1982 - tức là sau 44 năm.

HLV Unai Emery là "ông vua Europa League" khi đã 4 lần vô địch giải đấu này (3 lần với Sevilla, 1 lần với Villarreal). Ông từng là người thua trong trận chung kết UEL 2018-19 cùng Arsenal và giờ đang hướng đến danh hiệu thứ 5.

Về phong độ, Villa đã ghi 28 bàn và thủng lưới 8 bàn trong hành trình đến Istanbul, ít hơn Freiburg (25 bàn ghi, 10 bàn thủng lưới). Đặc biệt, Villa chưa thủng lưới trong 3 trận đấu trước đây tại Istanbul.

Trận chung kết bắt đầu lúc 21:00 giờ Trung Âu (tức 2:00 sáng 21/5 giờ Việt Nam)."""

# Dùng ảnh từ thư mục Arsenal/châu Âu (context châu Âu)
src_images_1 = sorted(
    (ROOT / "output/2026-05-17_220030_arteta-sap-vo-dich-champions-league/images").glob("*.jpg")
)[:6]
src_audio_1 = sorted(
    (ROOT / "output/2026-05-17_220030_arteta-sap-vo-dich-champions-league/audio").glob("*.mp3")
)[:6]


# ─────── TIN 2: ARSENAL vs PSG CL FINAL CẬP NHẬT ───────
title_2 = "Chung kết Champions League 2026: PSG bảo vệ ngôi vương, Arsenal đón lịch sử"
body_2 = """Paris Saint-Germain và Arsenal sẽ chạm trán trong trận chung kết UEFA Champions League 2026 vào ngày 30/5 tại sân Puskás Aréna ở Budapest, Hungary.

PSG đang cố gắng trở thành đội bóng thứ hai trong lịch sử kỷ nguyên Champions League bảo vệ thành công chức vô địch sau Real Madrid (2016-2018). Đội bóng Paris đã vượt qua Bayern Munich ở bán kết để tiến đến Budapest.

Arsenal đang đuổi theo chức vô địch Champions League đầu tiên trong lịch sử CLB. Các Pháo thủ đã đánh bại Atletico Madrid ở bán kết và giờ đây có cơ hội lịch sử. Trận chung kết năm 2006, Arsenal thua Barcelona 1-2 là lần duy nhất họ từng vào chung kết Champions League.

Trận đấu sẽ bắt đầu lúc 18:00 giờ Trung Âu (23:00 giờ Việt Nam) ngày 30/5. Sân Puskás Aréna có sức chứa 67.215 chỗ ngồi, từng tổ chức trận chung kết Europa League 2023.

Ban nhạc rock nổi tiếng The Killers sẽ biểu diễn trong lễ khai mạc trước trận đấu."""

src_images_2 = sorted(
    (ROOT / "output/2026-05-17_122027_arsenal-psg-cl-final-2026/images").glob("*.jpg")
)[:6]
src_audio_2 = sorted(
    (ROOT / "output/2026-05-17_122027_arsenal-psg-cl-final-2026/audio").glob("*.mp3")
)[:6]


# ─────── RUN ───────
print("=" * 60)
print("FOOTBALL VIDEO AGENT - SCHEDULED RUN 22:00 - 18/5/2026")
print("=" * 60)

results = []

print("\n--- Video 1: Europa League Final 2026 ---")
r1 = make_video(title_1, body_1, src_images_1, src_audio_1, "el_final_2026")
if r1:
    results.append(str(r1))

print("\n--- Video 2: Champions League Final 2026 preview ---")
r2 = make_video(title_2, body_2, src_images_2, src_audio_2, "cl_final_preview")
if r2:
    results.append(str(r2))


print("\n" + "=" * 60)
print(f"HOAN THANH: {len(results)}/2 video da tao")
for r in results:
    print(f"  OK {r}")
