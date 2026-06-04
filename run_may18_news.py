"""
Tạo video tin tức bóng đá ngày 18/5/2026 sử dụng tin tức mới nhất từ WebSearch.
Do proxy chặn kết nối web trong sandbox, script này sử dụng ảnh từ các video đã render trước
và tạo nội dung mới từ tin tức hôm nay.
"""
import sys
import os
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path("/sessions/gracious-wonderful-lamport/mnt/football-video-agent")
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

from scripts.script_gen import generate_script
from scripts.voice_gen import generate_all_voices
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

def make_video(title_vi: str, body_vi: str, source_images: list, story_key: str):
    """Tạo video từ text và danh sách ảnh nguồn."""
    OUTPUT_DIR = ROOT / "output"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    temp_slug = slugify_vi(title_vi)
    video_folder = OUTPUT_DIR / f"{timestamp}_{temp_slug}"
    images_dir = video_folder / "images"
    audio_dir = video_folder / "audio"
    frames_dir = video_folder / "frames"
    for d in (images_dir, audio_dir, frames_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Copy images từ nguồn
    valid_images = []
    from PIL import Image as PILImage
    for idx, src in enumerate(source_images, start=1):
        if len(valid_images) >= 8:
            break
        src_path = Path(src)
        if not src_path.exists():
            continue
        dst_path = images_dir / f"scene_{idx:02d}.jpg"
        shutil.copy2(src_path, dst_path)
        # Verify size
        with PILImage.open(dst_path) as img:
            if max(img.size) < 300:
                dst_path.unlink()
                continue
        valid_images.append(dst_path)

    num_scenes = len(valid_images)
    if num_scenes < 1:
        print(f"[{story_key}] Không có ảnh hợp lệ.")
        return None

    print(f"\n[{story_key}] Tạo script với {num_scenes} scenes...")
    scenes = generate_script(title_vi, body_vi, num_scenes=num_scenes)

    print(f"[{story_key}] Script:")
    for s in scenes:
        print(f"  [{s['id']}] {s.get('headline','')[:60]}")

    save_json(video_folder / "source.json", {
        "url": f"websearch_{story_key}_{timestamp}",
        "title_vi": title_vi,
        "body_vi": body_vi,
        "source_name": "websearch",
        "language": "vi",
        "was_translated": False,
        "num_scenes": num_scenes,
    })
    save_json(video_folder / "script.json", {"scenes": scenes})

    print(f"[{story_key}] Render frames...")
    render_all_scenes(scenes, images_dir, frames_dir)

    print(f"[{story_key}] Tạo voice...")
    generate_all_voices(scenes, audio_dir)

    print(f"[{story_key}] Compose video...")
    output_mp4 = video_folder / "video.mp4"
    result = compose_video(scenes, video_folder, output_mp4)

    print(f"\n✓ [{story_key}] HOÀN THÀNH: {output_mp4}")
    print(f"  Duration: {result['duration']:.1f}s, {num_scenes} scenes")
    return output_mp4

# ─────────────── TIN TỨC 18/5/2026 ───────────────

# Tin 1: Man City vô địch FA Cup 2026
title_1 = "Man City vô địch FA Cup 2026: Semenyo lập siêu phẩm đánh gót hạ Chelsea"
body_1 = """Manchester City giành chức vô địch FA Cup lần thứ 8 trong lịch sử sau khi đánh bại Chelsea 1-0 trong trận chung kết tại Wembley hôm thứ Bảy.

Antoine Semenyo, gia nhập Man City từ Bournemouth hồi tháng Giêng, là người hùng của trận đấu khi ghi bàn thắng duy nhất ở phút 72 bằng một cú đánh gót kỹ thuật đẳng cấp thế giới. Haaland phối hợp với Bernardo Silva trước khi tạm thời cho Semenyo, và tiền đạo người Ghana đã thực hiện cú đánh gót điệu nghệ, đưa bóng vào góc dưới cầu môn của thủ thành Robert Sanchez.

Semenyo đã ghi 10 bàn kể từ khi gia nhập Man City, đóng góp quan trọng vào 2 danh hiệu của đội bóng. Chiến thắng này là danh hiệu thứ 20 của HLV Pep Guardiola tại Anh, giúp ông thiết lập kỷ lục lịch sử Premier League.

Chelsea tiếp tục mùa giải thất vọng khi không có danh hiệu nào và nguy cơ không vào được Champions League mùa tới."""

# Sử dụng ảnh từ video FA Cup trước
source_images_1 = sorted(Path("/sessions/gracious-wonderful-lamport/mnt/football-video-agent/output/2026-05-17_041004_semenyo-lap-sieu-pham-fa-cup/images/").glob("*.jpg"))[:5]

# Tin 2: Bruno Fernandes lập kỷ lục kiến tạo Premier League
title_2 = "Bruno Fernandes sánh ngang Henry và De Bruyne: 20 kiến tạo Premier League một mùa"
body_2 = """Đội trưởng Man United Bruno Fernandes đã chính thức đi vào lịch sử Premier League sau khi cân bằng kỷ lục 20 kiến tạo trong một mùa giải, sánh ngang Thierry Henry (2002-03) và Kevin De Bruyne (2019-20).

Tiền vệ người Bồ Đào Nha lập kỷ lục này trong trận Man United gặp Nottingham Forest, khi tung ra đường chuyền chính xác từ cánh phải giúp Bryan Mbeumo ghi bàn. Đây là thành tích kiến tạo xuất sắc nhất trong sự nghiệp của Fernandes tại Anh.

Fernandes thừa nhận anh đã nghĩ đến kỷ lục này: "Khi chỉ còn kém họ một kiến tạo, tôi nghĩ về nó. Chúng ta đang nói về Kevin và Thierry - hai trong số những cầu thủ xuất sắc nhất Premier League từng chứng kiến. Tôi rất tự hào".

Fernandes đã giành giải FWA Cầu thủ xuất sắc nhất mùa và hiện có 102 kiến tạo trên mọi đấu trường cho Man United, chỉ sau Ryan Giggs, Wayne Rooney và David Beckham. Dưới sự dẫn dắt của HLV Michael Carrick, Man United đang có mùa giải ấn tượng."""

source_images_2 = sorted(Path("/sessions/gracious-wonderful-lamport/mnt/football-video-agent/output/2026-05-18_000722_bruno-can-ky-luc-henry-de-bruyne/images/").glob("*.jpg"))[:3]
# Thêm ảnh từ các video khác để đủ số lượng
extra_imgs = sorted(Path("/sessions/gracious-wonderful-lamport/mnt/football-video-agent/output/2026-05-17_015013_man-city-chelsea-ky-luc-buon" if Path("/sessions/gracious-wonderful-lamport/mnt/football-video-agent/output/2026-05-17_015013_man-city-chelsea-ky-luc-buon").exists() else "/sessions/gracious-wonderful-lamport/mnt/football-video-agent/output/2026-05-17_002505_man-city-chelsea-ky-luc-buon").glob("*.jpg")) if Path("/sessions/gracious-wonderful-lamport/mnt/football-video-agent/output").glob("*man-city*") else []

print("="*60)
print("FOOTBALL VIDEO AGENT - SCHEDULED RUN 2AM - 18/5/2026")
print("="*60)

results = []

print("\n--- Video 1: FA Cup Final ---")
r1 = make_video(title_1, body_1, source_images_1, "fa_cup_final")
if r1:
    results.append(str(r1))

print("\n--- Video 2: Bruno Fernandes Record ---")
r2 = make_video(title_2, body_2, source_images_2, "bruno_record")
if r2:
    results.append(str(r2))

print("\n" + "="*60)
print(f"HOÀN THÀNH: {len(results)}/{2} video được tạo thành công")
for r in results:
    print(f"  ✓ {r}")
