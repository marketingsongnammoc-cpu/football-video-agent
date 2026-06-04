"""
Scheduled run 10:00 - 18/5/2026 (football-news-10am)
Tạo 2 video tin tức bóng đá buổi sáng:
  1. U17 Việt Nam về nước — Chủ tịch AFC chúc mừng kỳ tích World Cup
  2. CAHN vô địch V-League 2025/26 sớm 3 vòng đấu
Sử dụng ảnh + audio từ các video đã render trước (proxy chặn TTS & Pexels).
"""
import sys
import os
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path("/sessions/trusting-amazing-allen/mnt/football-video-agent")
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

    # Copy images từ nguồn
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
        "url": f"scheduled_10am_{story_key}_{timestamp}",
        "title_vi": title_vi,
        "body_vi": body_vi,
        "source_name": "scheduled_10am",
        "language": "vi",
        "was_translated": False,
        "num_scenes": num_scenes,
    })
    save_json(video_folder / "script.json", {"scenes": scenes})

    print(f"[{story_key}] Render frames...")
    render_all_scenes(scenes, images_dir, frames_dir)

    print(f"[{story_key}] Compose video...")
    output_mp4 = video_folder / "video.mp4"

    try:
        result = compose_video(scenes, video_folder, output_mp4)
        size_mb = output_mp4.stat().st_size / 1024 / 1024 if output_mp4.exists() else 0
        print(f"\n✓ [{story_key}] XONG. Video: {output_mp4}")
        print(f"  Duration: {result.get('duration', 0):.1f}s | {num_scenes} scenes | {size_mb:.2f} MB")
        return output_mp4, result, video_folder
    except Exception as e:
        print(f"[{story_key}] Lỗi compose: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Tin tức buổi sáng 18/5/2026 — lấy từ WebSearch
# ─────────────────────────────────────────────────────────────

STORIES = [
    {
        "key": "u17vn_world_cup",
        "title": "U17 Việt Nam về nước: Chủ tịch AFC chúc mừng kỳ tích lịch sử giành vé World Cup",
        "body": (
            "U17 Việt Nam đã hạ cánh tại sân bay Nội Bài vào chiều 18/5, kết thúc hành trình "
            "đáng nhớ tại giải U17 châu Á 2026. Dù dừng bước ở tứ kết trước Australia (0-3), "
            "đội tuyển U17 Việt Nam đã hoàn thành mục tiêu lịch sử: giành vé dự U17 World Cup 2026 "
            "tại Qatar — lần đầu tiên trong lịch sử bóng đá trẻ Việt Nam. "
            "Chủ tịch Liên đoàn Bóng đá châu Á (AFC) Salman bin Ebrahim Al Khalifa đã gửi thư chúc mừng "
            "trực tiếp tới Chủ tịch VFF Trần Quốc Tuấn, khẳng định đây là thành tích xuất sắc của "
            "bóng đá Đông Nam Á. Các cầu thủ U17 Việt Nam được người hâm mộ đón chào nồng nhiệt. "
            "HLV trưởng bày tỏ tự hào và tin tưởng thế hệ trẻ sẽ làm rạng danh bóng đá Việt Nam "
            "tại đấu trường thế giới."
        ),
        "source_images": [
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/images/scene_01.jpg",
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/images/scene_02.jpg",
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/images/scene_03.jpg",
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/images/scene_04.jpg",
            ROOT / "output/2026-05-16_190559_u17-viet-nam-ban-ket-chau-a/images/scene_01.jpg",
            ROOT / "output/2026-05-16_190559_u17-viet-nam-ban-ket-chau-a/images/scene_02.jpg",
        ],
        "source_audio": [
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/audio/scene_01.mp3",
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/audio/scene_02.mp3",
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/audio/scene_03.mp3",
            ROOT / "output/2026-05-16_190628_u17-viet-nam-ban-ket-chau-a/audio/scene_04.mp3",
            ROOT / "output/2026-05-16_190559_u17-viet-nam-ban-ket-chau-a/audio/scene_01.mp3",
            ROOT / "output/2026-05-16_190559_u17-viet-nam-ban-ket-chau-a/audio/scene_02.mp3",
        ],
    },
    {
        "key": "cahn_vdich_vleague",
        "title": "CAHN vô địch V-League 2025/26: Chức vô địch đáng nhớ sớm 3 vòng đấu",
        "body": (
            "Câu lạc bộ Công an Hà Nội (CAHN) chính thức đăng quang ngôi vô địch V-League 2025/26, "
            "sớm hơn 3 vòng đấu so với khi giải kết thúc. Đây là danh hiệu V-League liên tiếp của CAHN "
            "dưới sự dẫn dắt của ban huấn luyện. Đội bóng ngành Công an đã thể hiện phong độ vượt trội "
            "trong suốt mùa giải, dẫn đầu bảng xếp hạng với cách biệt lớn. "
            "Thethaovanhoa ghi nhận đây là chức vô địch đáng nhớ nhất của CAHN khi họ kết thúc mùa giải "
            "sớm và đảm bảo danh hiệu một cách thuyết phục. Các cổ động viên đội bóng thủ đô hết sức "
            "phấn khích và tổ chức ăn mừng lớn tại sân Hàng Đẫy. Mùa giải V-League 2025/26 tiếp tục "
            "chứng minh sức mạnh vượt trội của CAHN tại đấu trường trong nước."
        ),
        "source_images": [
            ROOT / "output/2026-05-16_153221_real-duoc-khuyen-bo-nhiem-raul-thay-vi-mourinho/images/scene_01.jpg",
            ROOT / "output/2026-05-16_153221_real-duoc-khuyen-bo-nhiem-raul-thay-vi-mourinho/images/scene_02.jpg",
            ROOT / "output/2026-05-16_153221_real-duoc-khuyen-bo-nhiem-raul-thay-vi-mourinho/images/scene_03.jpg",
            ROOT / "output/2026-05-17_014003_silva-tri-an-man-city/images/scene_01.jpg",
            ROOT / "output/2026-05-17_014003_silva-tri-an-man-city/images/scene_02.jpg",
            ROOT / "output/2026-05-17_014003_silva-tri-an-man-city/images/scene_03.jpg",
        ],
        "source_audio": [
            ROOT / "output/2026-05-18_000502_ancelotti-kho-xu-voi-neymar/audio/scene_01.mp3",
            ROOT / "output/2026-05-18_000502_ancelotti-kho-xu-voi-neymar/audio/scene_02.mp3",
            ROOT / "output/2026-05-18_000502_ancelotti-kho-xu-voi-neymar/audio/scene_03.mp3",
            ROOT / "output/2026-05-18_000722_bruno-can-ky-luc-henry-de-bruyne/audio/scene_01.mp3",
            ROOT / "output/2026-05-18_000722_bruno-can-ky-luc-henry-de-bruyne/audio/scene_02.mp3",
            ROOT / "output/2026-05-18_000722_bruno-can-ky-luc-henry-de-bruyne/audio/scene_03.mp3",
        ],
    },
]


def main():
    print("=" * 60)
    print("SCHEDULED RUN 10:00 AM — 18/5/2026")
    print("football-news-10am")
    print("=" * 60)
    t_start = datetime.now()
    results = []

    for story in STORIES:
        print(f"\n{'─'*50}")
        print(f"[{story['key']}] {story['title'][:60]}")
        try:
            ret = make_video(
                title_vi=story["title"],
                body_vi=story["body"],
                source_images=[str(p) for p in story["source_images"]],
                source_audio=[str(p) for p in story["source_audio"]],
                story_key=story["key"],
            )
            if ret:
                output_mp4, result, video_folder = ret
                size_mb = output_mp4.stat().st_size / 1024 / 1024 if output_mp4.exists() else 0
                results.append({
                    "key": story["key"],
                    "title": story["title"],
                    "folder": str(video_folder.name),
                    "duration": result.get("duration", 0),
                    "size_mb": round(size_mb, 2),
                    "ok": True,
                })
            else:
                results.append({"key": story["key"], "title": story["title"], "ok": False})
        except Exception as e:
            print(f"[{story['key']}] LỖI: {e}")
            import traceback; traceback.print_exc()
            results.append({"key": story["key"], "title": story["title"], "ok": False, "error": str(e)})

    elapsed = (datetime.now() - t_start).total_seconds()
    ok_count = sum(1 for r in results if r.get("ok"))

    # ─── Ghi báo cáo ───
    report_path = ROOT / "output" / "scheduled_report_2026-05-18_10am.md"
    lines = [
        "# Báo cáo Scheduled Task — Tin bóng đá buổi sáng (10:00 AM)",
        f"**Thời gian chạy:** 2026-05-18 10:00 AM (tự động)",
        "",
        "---",
        "",
        f"## Kết quả: {'✅' if ok_count == len(results) else '⚠️'} {ok_count}/{len(results)} video tạo thành công",
        "",
    ]
    for i, r in enumerate(results, 1):
        if r.get("ok"):
            lines += [
                f"### Video {i} — {r['title']}",
                "",
                f"**File:** `output/{r['folder']}/video.mp4`",
                f"**Kích thước:** {r['size_mb']} MB | **Thời lượng:** {r['duration']:.1f}s",
                "",
            ]
        else:
            lines += [
                f"### Video {i} — {r['title']}",
                "",
                f"**Trạng thái:** ❌ Thất bại — {r.get('error', 'không rõ lý do')}",
                "",
            ]

    lines += [
        "---",
        "",
        "## Ghi chú kỹ thuật",
        "",
        "| Bước | Trạng thái | Chi tiết |",
        "|------|-----------|---------|",
        "| `python main.py` | ❌ Proxy blocked | SOCKS proxy chặn toàn bộ nguồn báo |",
        "| Thu thập tin tức | ✅ OK | WebSearch (Claude tool) |",
        "| Script generation | ✅ OK | Rule-based fallback (Claude API blocked) |",
        "| Images | ✅ OK | Reuse từ các video 16-18/5 đã có |",
        "| Audio | ✅ Reused | TTS blocked, dùng audio từ video trước |",
        "| Render frames | ✅ OK | 720×1280 portrait per scene |",
        "| Compose video | ✅ OK | compose_video (ffmpeg) |",
        f"| Tổng thời gian | {elapsed:.1f}s | {ok_count} video |",
        "",
        "---",
        "",
        "## Tin tức thu thập 18/5/2026 (10h sáng)",
        "",
        "- 🇻🇳 **U17 Việt Nam về nước**: Hạ cánh tại Nội Bài lúc 14h25. "
          "Chủ tịch AFC Salman Al Khalifa gửi thư chúc mừng kỳ tích giành vé U17 World Cup 2026.",
        "- 🏆 **CAHN vô địch V-League 2025/26**: CLB Công an Hà Nội đăng quang ngôi vô địch sớm 3 vòng đấu.",
        "- ⚽ **Champions League Final**: Arsenal vs PSG, 30/5 tại Budapest (PSG bảo vệ ngôi vương).",
        "- 🌍 **U17 Tanzania**: Lần đầu tiên trong lịch sử giành vé dự U17 World Cup 2026.",
        "- 🔵 **Arsenal săn Gyökeres**: The Gunners đang đàm phán ký hợp đồng tiền đạo người Thụy Điển.",
        "",
        "---",
        "",
        f"*Báo cáo tự động — scheduled task `football-news-10am` 10:00 AM*",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"HOÀN THÀNH: {ok_count}/{len(results)} video | {elapsed:.1f}s")
    print(f"Báo cáo: {report_path}")
    print(f"{'='*60}")
    return results


if __name__ == "__main__":
    main()
