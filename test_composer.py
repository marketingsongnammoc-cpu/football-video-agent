"""
test_composer.py — Test composer Ken Burns với N scenes (mock data).
Không cần API key. Dùng silence audio để test motion.
"""

import sys
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from scene_renderer import render_all_scenes
from composer import compose_video


def make_mock_image(width: int, height: int, label: str, output: Path,
                    bg_color=(30, 80, 50), accent=(40, 120, 70)) -> None:
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    for x in range(0, width, 80):
        draw.line([(x, 0), (x, height)], fill=accent, width=2)
    for y in range(0, height, 80):
        draw.line([(0, y), (width, y)], fill=accent, width=2)
    cx, cy = width // 2, height // 2
    r = min(width, height) // 4
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(80, 160, 100))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, (height - th) // 2), label, font=font, fill=(255, 255, 255))
    img.save(output, "JPEG", quality=92)


def make_silent_audio(duration: float, output: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", str(duration), "-q:a", "9", "-acodec", "libmp3lame",
         "-y", str(output)],
        check=True, capture_output=True,
    )


def main():
    out_dir = Path("/tmp/test_composer")
    out_dir.mkdir(exist_ok=True)
    images_dir = out_dir / "images"
    frames_dir = out_dir / "frames"
    audio_dir = out_dir / "audio"
    for d in (images_dir, frames_dir, audio_dir):
        d.mkdir(exist_ok=True)

    # 5 scenes với aspect ratio khác nhau (test scaling)
    print("1. Tạo 5 ảnh mock...")
    aspects = [
        (1600, 900, "16:9", (40, 80, 120), (60, 120, 180)),
        (1200, 800, "3:2", (120, 60, 60), (180, 90, 90)),
        (1000, 1000, "1:1", (60, 100, 40), (90, 150, 60)),
        (1800, 1200, "3:2", (80, 80, 120), (120, 120, 180)),
        (1400, 800, "16:9", (120, 80, 60), (180, 120, 90)),
    ]
    for i, (w, h, label, bg, ac) in enumerate(aspects, 1):
        make_mock_image(w, h, f"SCENE {i}\n{label}", images_dir / f"scene_{i:02d}.jpg",
                        bg_color=bg, accent=ac)

    scenes = [
        {
            "id": "01",
            "headline": "Hà Nội FC khởi đầu mạnh",
            "subtext": "Đội bóng thủ đô vào sân với quyết tâm cao.",
            "tag": "⚽ TRẬN ĐẤU",
            "accent": "emerald",
        },
        {
            "id": "02",
            "headline": "Văn Quyết mở tỉ số phút 23",
            "subtext": "Pha xử lý cá nhân đẹp mắt của đội trưởng.",
            "tag": "👤 NGÔI SAO",
            "accent": "cyan",
        },
        {
            "id": "03",
            "headline": "Tuấn Hải nhân đôi cách biệt",
            "subtext": "Phút 56, hàng công Hà Nội bùng nổ.",
            "tag": "⚽ TRẬN ĐẤU",
            "accent": "amber",
        },
        {
            "id": "04",
            "headline": "Hùng Dũng ấn định 3-0",
            "subtext": "Cú đá phạt đẹp phút 78 khép lại trận đấu.",
            "tag": "🎯 CHIẾN THUẬT",
            "accent": "red",
        },
        {
            "id": "05",
            "headline": "Hà Nội bám đuổi ngôi đầu V-League",
            "subtext": "Ba điểm trọn vẹn giúp đội bóng giữ vị trí top.",
            "tag": "🏆 GIẢI ĐẤU",
            "accent": "emerald",
        },
    ]

    print("\n2. Render bg + overlay cho 5 scenes...")
    render_all_scenes(scenes, images_dir, frames_dir)

    print("\n3. Tạo audio mock (silence 3s/scene)...")
    for s in scenes:
        make_silent_audio(3.0, audio_dir / f"scene_{s['id']}.mp3")
    print(f"   ✓ {len(scenes)} audio files")

    print("\n4. Composer ghép video...")
    output_mp4 = out_dir / "video.mp4"
    result = compose_video(scenes, out_dir, output_mp4, seed=42)

    print(f"\n✓ Hoàn tất!")
    print(f"  Duration: {result['duration']:.1f}s ({len(scenes)} scenes)")
    print(f"  Output: {output_mp4}")
    for sm in result["scenes_meta"]:
        print(f"  - scene {sm['id']}: {sm['motion']} ({sm['duration']:.1f}s)")
    return output_mp4


if __name__ == "__main__":
    main()
