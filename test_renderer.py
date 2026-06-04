"""
test_renderer.py — Test scene_renderer với 3 aspect ratio khác nhau
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from scene_renderer import render_scene, render_all_scenes


def make_mock_image(width: int, height: int, label: str, output: Path,
                    bg_color=(30, 80, 50), accent=(40, 120, 70)) -> None:
    """Tạo ảnh fake có pattern + label để dễ nhận diện trong test."""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    # Vẽ pattern lưới
    for x in range(0, width, 80):
        draw.line([(x, 0), (x, height)], fill=accent, width=2)
    for y in range(0, height, 80):
        draw.line([(0, y), (width, y)], fill=accent, width=2)
    # Vẽ tròn lớn ở giữa cho dễ nhận biết
    cx, cy = width // 2, height // 2
    r = min(width, height) // 4
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(80, 160, 100))
    # Label
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, (height - th) // 2), label, font=font, fill=(255, 255, 255))
    img.save(output, "JPEG", quality=92)


def main():
    out_dir = Path("/tmp/test_render")
    out_dir.mkdir(exist_ok=True)
    images_dir = out_dir / "images"
    frames_dir = out_dir / "frames"
    images_dir.mkdir(exist_ok=True)
    frames_dir.mkdir(exist_ok=True)

    # 3 scenes với 3 aspect khác nhau để test 3 layout
    print("Tạo 3 ảnh mock với 3 aspect ratio khác nhau...")

    # Scene 01: ảnh ngang (landscape) → Layout A
    make_mock_image(1600, 900, "LANDSCAPE 16:9", images_dir / "scene_01.jpg",
                    bg_color=(40, 80, 120), accent=(60, 120, 180))
    # Scene 02: ảnh vuông → Layout B
    make_mock_image(1000, 1000, "SQUARE 1:1", images_dir / "scene_02.jpg",
                    bg_color=(120, 60, 60), accent=(180, 90, 90))
    # Scene 03: ảnh dọc → Layout C
    make_mock_image(720, 1080, "PORTRAIT 2:3", images_dir / "scene_03.jpg",
                    bg_color=(60, 100, 40), accent=(90, 150, 60))

    # Mock scenes data — có cả text dài để test smart word-wrap
    scenes = [
        {
            "id": "01",
            "headline": "Đà Nẵng thi đấu quả cảm để giữ ngôi đầu",  # 8 từ, sẽ wrap
            "subtext": "CA TPHCM bước vào trận đấu với mục tiêu giành 3 điểm.",  # 12 từ
            "tag": "⚽ TRẬN ĐẤU",
            "accent": "emerald",
        },
        {
            "id": "02",
            "headline": "Lee Williams ghi bàn từ chấm phạt đền",  # 7 từ
            "subtext": "Cầu thủ trẻ hoàn thành nhiệm vụ gỡ hòa quan trọng.",  # 10 từ
            "tag": "👤 NGÔI SAO",
            "accent": "cyan",
        },
        {
            "id": "03",
            "headline": "Trận đấu khép lại với hai tiếng còi",  # 7 từ
            "subtext": "Một điểm rời sân Thống Nhất là phần thưởng xứng đáng cho cả hai.",  # 13 từ
            "tag": "🏆 GIẢI ĐẤU",
            "accent": "amber",
        },
    ]

    print("\nRender 3 scenes...")
    results = render_all_scenes(scenes, images_dir, frames_dir)

    print("\n✓ Hoàn tất. Output:")
    for r in results:
        sid = r["scene_id"]
        print(f"  - {frames_dir}/scene_{sid}.png")
    return frames_dir


if __name__ == "__main__":
    main()
