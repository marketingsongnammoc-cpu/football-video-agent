"""
run_3_videos.py — Tạo 3 video và đăng theo lịch:
  - Video 1: đăng ngay
  - Video 2: đăng sau 30 phút
  - Video 3: đăng sau 60 phút

Chạy:
  python run_3_videos.py
  python run_3_videos.py --branch vn
  python run_3_videos.py --branch tabloid
  python run_3_videos.py --dry-run
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

from main import run_auto_fetch
from scripts.publisher import publish_video, make_caption

DELAY_MINUTES = [0, 30, 60]


def main():
    parser = argparse.ArgumentParser(description="Tạo 3 video và đăng theo lịch")
    parser.add_argument("--branch", choices=["vn", "tabloid"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("BATCH: Tạo 3 video và đăng theo lịch")
    print("  Bài 1 → đăng ngay")
    print("  Bài 2 → đăng sau 30 phút")
    print("  Bài 3 → đăng sau 60 phút")
    print("=" * 60)

    # Tạo 3 video, mỗi lần fetch 1 bài (để lấy 3 bài khác nhau từ cùng nguồn)
    videos = []
    for attempt in range(1, 4):
        print(f"\n[batch] Tạo video {attempt}/3...")
        result = run_auto_fetch(
            branch=args.branch,
            max_articles=1,
            dry_run=args.dry_run,
            no_publish=True,
        )
        if result:
            videos.extend(result)
        else:
            print(f"  [batch] Không tạo được video {attempt}, thử tiếp.")

    if not videos:
        print("\n[batch] Không tạo được video nào. Kiểm tra nguồn tin và log.")
        return

    print(f"\n[batch] Tạo được {len(videos)} video. Bắt đầu đăng...")

    for i, video_path in enumerate(videos):
        delay = DELAY_MINUTES[i] if i < len(DELAY_MINUTES) else DELAY_MINUTES[-1] + i * 30
        video_folder = video_path.parent

        # Load script + source để tạo caption
        try:
            script = json.loads((video_folder / "script.json").read_text(encoding="utf-8"))
            source = json.loads((video_folder / "source.json").read_text(encoding="utf-8"))
            caption = make_caption(source["title_vi"], script["scenes"])
        except Exception as e:
            print(f"  [batch] Video {i+1}: lỗi đọc metadata ({e}), dùng caption đơn giản.")
            caption = f"Tin bóng đá nóng nhất! #bongda #football #tintucbongda"

        label = "đăng ngay" if delay == 0 else f"đăng sau {delay} phút"
        print(f"\n[batch] Video {i+1}/{len(videos)}: {video_path.name} → {label}")

        if args.dry_run:
            print(f"  [dry-run] Bỏ qua bước đăng.")
            continue

        result = publish_video(video_path, caption, delay_minutes=delay)
        if result:
            print(f"  [batch] ✓ Video {i+1} đã được xử lý (post ID: {result.get('id', '?')})")
        else:
            print(f"  [batch] ✗ Video {i+1} đăng thất bại.")

    print(f"\n[batch] Hoàn tất. {len(videos)} video đã được lên lịch.")


if __name__ == "__main__":
    main()
