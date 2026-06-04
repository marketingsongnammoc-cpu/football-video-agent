"""
publish_one.py — Đăng 1 video từ folder đã render sẵn.
Usage: python publish_one.py <video_folder>
"""
from __future__ import annotations
import sys
import json
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

from scripts.publisher import publish_video, make_caption


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--delay", type=int, default=0, help="Đăng sau N phút (0=ngay)")
    args = parser.parse_args()

    folder = Path(args.folder)
    video_path = folder / "video.mp4"

    if not video_path.exists():
        print(f"[publish_one] Không tìm thấy video: {video_path}")
        sys.exit(1)

    script = json.loads((folder / "script.json").read_text(encoding="utf-8"))
    source = json.loads((folder / "source.json").read_text(encoding="utf-8"))

    caption = make_caption(source["title_vi"], script["scenes"])
    label = "ngay" if args.delay == 0 else f"sau {args.delay} phút"
    print(f"[publish_one] Đăng ({label}): {folder.name}")

    result = publish_video(video_path, caption, delay_minutes=args.delay)
    if result:
        print(f"[publish_one] ✓ Đăng thành công! Post ID: {result.get('id', '?')}")
    else:
        print("[publish_one] ✗ Đăng thất bại.")
        sys.exit(1)


if __name__ == "__main__":
    main()
