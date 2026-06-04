"""
main.py — Entry point football-video-agent.

CHẾ ĐỘ CHẠY:
  python main.py                           # Auto-fetch tất cả 10 nguồn
  python main.py --branch vn               # Chỉ nhánh VN
  python main.py --branch tabloid          # Chỉ nhánh tabloid
  python main.py --source bongda           # 1 nguồn cụ thể
  python main.py --url "https://..."       # URL chỉ định
  python main.py --text "..."              # Mode B từ text
  python main.py --dry-run                 # Chỉ sinh script, không render/voice/video
  python main.py --recompose <folder>      # Re-compose video từ folder có sẵn
"""

from __future__ import annotations
import argparse
import json
import sys
import os
import time

# UTF-8 console (Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import unicodedata
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Setup path để import scripts.* khi chạy main.py
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Load .env
load_dotenv(ROOT / "config" / ".env")

from scripts.fetcher import (
    load_sources_config, get_adapter, detect_adapter_from_url,
    list_all_sources, ADAPTER_REGISTRY,
)
from scripts.fetcher.base import Article
from scripts.content_filter import check_article
from scripts.translator import translate_article
from scripts.script_gen import generate_script
from scripts.voice_gen import generate_all_voices
from scripts.scene_renderer import render_all_scenes
from scripts.composer import compose_video
from scripts.hot_scorer import score_article
from scripts.publisher import publish_video, make_caption


CONFIG_PATH = ROOT / "config" / "sources.json"
OUTPUT_DIR = ROOT / "output"
DATA_DIR = ROOT / "data"
PROCESSED_FILE = DATA_DIR / "processed.json"
SKIPPED_FILE = DATA_DIR / "skipped.json"
import platform as _platform
LOCK_FILE = Path("/tmp" if _platform.system() != "Windows" else os.environ.get("TEMP", "C:/Windows/Temp")) / ".football-main.lock"


# ───────────────────────────────────────────────────────────
# Process lock — ngăn 2 instance chạy đồng thời
# ───────────────────────────────────────────────────────────

def _acquire_lock() -> bool:
    """Ghi PID vào lockfile. Trả về False nếu instance khác đang chạy."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            if _platform.system() == "Windows":
                import ctypes
                handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    print(f"[main] Instance khác đang chạy (PID {pid}), bỏ qua.")
                    return False
            else:
                try:
                    os.kill(pid, 0)
                    print(f"[main] Instance khác đang chạy (PID {pid}), bỏ qua.")
                    return False
                except ProcessLookupError:
                    pass  # Process đã chết
                except PermissionError:
                    print(f"[main] Instance khác đang chạy (PID {pid}), bỏ qua.")
                    return False
        except Exception:
            pass  # PID không hợp lệ
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


# ───────────────────────────────────────────────────────────
# Download helper — dùng temp file để tránh file lock (WinError 32)
# ───────────────────────────────────────────────────────────

def _download_image(url: str, out_path: Path,
                    session, min_side: int = 400) -> bool:
    """
    Tải hình về out_path qua temp file để tránh Windows Defender lock.
    Trả về True nếu thành công và hình đủ kích thước.
    """
    import tempfile
    from PIL import Image as PILImage
    tmp_path = None
    try:
        resp = session.get(url, timeout=30, stream=True,
                           headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Ghi vào temp file cùng thư mục (để rename atomic trên cùng ổ đĩa)
        fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=out_path.parent)
        tmp_path = Path(tmp)
        with os.fdopen(fd, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        # Validate kích thước
        with PILImage.open(tmp_path) as img:
            if min(img.size) < min_side:
                return False
        # Rename atomic — tránh race condition
        os.replace(tmp_path, out_path)
        tmp_path = None
        return True
    except Exception:
        return False
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ───────────────────────────────────────────────────────────
# Tracking
# ───────────────────────────────────────────────────────────

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_processed(url: str, video_folder: Path) -> None:
    data = load_json(PROCESSED_FILE, [])
    data.append({
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "folder": str(video_folder.relative_to(ROOT)) if video_folder.is_relative_to(ROOT) else str(video_folder),
    })
    save_json(PROCESSED_FILE, data)


def mark_skipped(url: str, reason: str, source: str = "", error: str = "") -> None:
    data = load_json(SKIPPED_FILE, [])
    data.append({
        "url": url,
        "source": source,
        "reason": reason,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    })
    save_json(SKIPPED_FILE, data)


def is_url_processed(url: str) -> bool:
    data = load_json(PROCESSED_FILE, [])
    return any(item.get("url") == url for item in data)


# ───────────────────────────────────────────────────────────
# Slug helper
# ───────────────────────────────────────────────────────────

def slugify_vi(text: str, max_len: int = 50) -> str:
    """Bỏ dấu tiếng Việt + lowercase + thay non-alphanum thành '-'."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "d").lower()
    # Replace non-alphanum bằng '-'
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug[:max_len]


# ───────────────────────────────────────────────────────────
# Pipeline cho 1 bài
# ───────────────────────────────────────────────────────────

def process_article(article: Article, is_tabloid: bool, dry_run: bool = False,
                    no_publish: bool = False) -> Path | None:
    """
    Chạy full pipeline cho 1 bài.
    Returns: path video.mp4 nếu thành công, None nếu skip.
    """
    url = article.url
    print(f"\n{'='*60}")
    print(f"Bài: {article.title}")
    print(f"Nguồn: {article.source_name} ({article.language})")
    print(f"URL: {url}")
    print(f"Hình: {len(article.images)} ảnh")

    # 1. Content filter (cho tabloid) + check tối thiểu 500 ký tự body
    passed, reason = check_article(url, article.title, article.body, is_tabloid)
    if not passed:
        print(f"  ✗ Bài bị filter: {reason}")
        mark_skipped(url, reason, article.source_name)
        return None
    if len(article.body) < 500:
        print(f"  ✗ Body quá ngắn ({len(article.body)} ký tự < 500).")
        mark_skipped(url, "body_too_short", article.source_name)
        return None

    # 2. Dịch nếu cần
    title_vi, body_vi = article.title, article.body
    if article.language != "vi":
        try:
            title_vi, body_vi = translate_article(article.title, article.body, article.language)
        except Exception as e:
            print(f"  ✗ Dịch thất bại: {e}")
            mark_skipped(url, "translation_failed", article.source_name, str(e))
            return None

    # 3. Kiểm tra hình — bỏ qua bài không có ảnh
    if len(article.images) < 1:
        print(f"  ✗ Bài không có hình → bỏ qua.")
        mark_skipped(url, "no_images", article.source_name)
        return None

    # 4. Tạo folder video (slug dựa trên title trước khi có script)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    temp_slug = slugify_vi(title_vi)
    video_folder = OUTPUT_DIR / f"{timestamp}_{temp_slug}"
    images_dir = video_folder / "images"
    audio_dir = video_folder / "audio"
    frames_dir = video_folder / "frames"
    for d in (images_dir, audio_dir, frames_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 5. Tải hình từ bài (tối đa MAX_SCENES)
    MAX_SCENES = 5
    MIN_SCENES = 4  # tái sử dụng ảnh nếu bài có ít hơn số này
    candidate_imgs = article.images[:MAX_SCENES * 3]  # thử nhiều hơn để đủ valid
    print(f"\n--- TẢI HÌNH (tối đa {MAX_SCENES} ảnh từ {len(candidate_imgs)} candidates) ---")
    import requests
    import shutil
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    downloaded_images: list[Path] = []
    save_idx = 1
    for idx, img_url in enumerate(candidate_imgs, start=1):
        if len(downloaded_images) >= MAX_SCENES:
            break
        out_path = images_dir / f"scene_{save_idx:02d}.jpg"
        if not _download_image(img_url, out_path, session):
            print(f"  ✗ scene {idx:02d}: hình quá nhỏ hoặc lỗi tải")
            continue
        downloaded_images.append(out_path)
        print(f"  ✓ scene {save_idx:02d}: {img_url[:60]}...")
        save_idx += 1

    num_scenes = len(downloaded_images)
    if num_scenes < 1:
        print(f"  ✗ Không có hình hợp lệ từ bài báo.")
        mark_skipped(url, "no_valid_images", article.source_name)
        return None

    # Tái sử dụng ảnh nếu không đủ MIN_SCENES
    if num_scenes < MIN_SCENES:
        print(f"  → Chỉ có {num_scenes} ảnh, tái sử dụng để đủ {MIN_SCENES} scenes...")
        original_images = downloaded_images.copy()
        i = 0
        while len(downloaded_images) < MIN_SCENES:
            src = original_images[i % len(original_images)]
            dst = images_dir / f"scene_{save_idx:02d}.jpg"
            shutil.copy2(src, dst)
            downloaded_images.append(dst)
            print(f"  ↺ scene {save_idx:02d}: tái sử dụng {src.name}")
            save_idx += 1
            i += 1
        num_scenes = len(downloaded_images)

    print(f"\n  → Tổng {num_scenes} hình → sẽ tạo {num_scenes} scenes")

    # 6. Sinh script (số scenes = số hình)
    try:
        scenes = generate_script(title_vi, body_vi, num_scenes=num_scenes)
    except Exception as e:
        print(f"  ✗ Script_gen thất bại: {e}")
        mark_skipped(url, "script_gen_failed", article.source_name, str(e))
        return None

    # Cap scenes theo số ảnh thực tế (script_gen đôi khi trả về nhiều hơn)
    scenes = scenes[:num_scenes]

    # Gắn image_url cho từng scene
    for i, scene in enumerate(scenes):
        scene["image_url"] = str(downloaded_images[i])

    print("\n--- SCRIPT ---")
    for s in scenes:
        print(f"  [{s['id']}] {s['tag']}")
        print(f"        Headline: {s['headline']}")
        print(f"        Subtext:  {s['subtext']}")
        print(f"        Narration: {s['narration'][:80]}...")

    if dry_run:
        print("\n[dry-run] Dừng tại đây.")
        return None

    # Đổi tên folder nếu có slug từ headline scene 1 (đẹp hơn)
    final_slug = slugify_vi(scenes[0]["headline"])
    if final_slug != temp_slug:
        new_folder = OUTPUT_DIR / f"{timestamp}_{final_slug}"
        if not new_folder.exists():
            video_folder.rename(new_folder)
            video_folder = new_folder
            images_dir = video_folder / "images"
            audio_dir = video_folder / "audio"
            frames_dir = video_folder / "frames"

    # Save metadata
    save_json(video_folder / "source.json", {
        "url": url,
        "title_original": article.title,
        "body_original": article.body,
        "title_vi": title_vi,
        "body_vi": body_vi,
        "source_name": article.source_name,
        "language": article.language,
        "was_translated": article.language != "vi",
        "is_tabloid": is_tabloid,
        "num_scenes": num_scenes,
    })
    save_json(video_folder / "script.json", {"scenes": scenes})

    # 7. Render bg + overlay
    print("\n--- RENDER FRAMES ---")
    render_all_scenes(scenes, images_dir, frames_dir)

    # 8. Voice
    print("\n--- VOICE ---")
    generate_all_voices(scenes, audio_dir)

    # 9. Compose video
    print("\n--- COMPOSE VIDEO ---")
    output_mp4 = video_folder / "video.mp4"
    result = compose_video(scenes, video_folder, output_mp4)
    print(f"\n✓ XONG. Video: {output_mp4}")
    print(f"  Duration: {result['duration']:.1f}s, {num_scenes} scenes")

    mark_processed(url, video_folder)

    # 10. Publish lên TikTok + Facebook (nếu có WOOPSOCIAL_API_KEY)
    if not no_publish:
        print("\n--- ĐĂNG VIDEO ---")
        caption = make_caption(title_vi, scenes)
        publish_video(output_mp4, caption)

    return output_mp4


# ───────────────────────────────────────────────────────────
# Routing
# ───────────────────────────────────────────────────────────

def run_url(url: str, dry_run: bool = False, no_publish: bool = False) -> Path | None:
    """Mode A — URL chỉ định."""
    configs = load_sources_config(CONFIG_PATH)
    source_key = detect_adapter_from_url(url, configs)
    adapter = get_adapter(source_key, configs)
    print(f"[main] Source: {source_key}")
    article = adapter.fetch_article(url)
    return process_article(article, configs[source_key].tabloid, dry_run, no_publish)


def run_auto_fetch(branch: str | None = None, source: str | None = None,
                   dry_run: bool = False, max_articles: int = 1,
                   no_publish: bool = False) -> list[Path]:
    """Mode A — auto-fetch theo Hot Scorer score."""
    configs = load_sources_config(CONFIG_PATH)

    if source:
        if source not in ADAPTER_REGISTRY:
            print(f"[main] Source '{source}' chưa có adapter. Available: {list(ADAPTER_REGISTRY.keys())}")
            return []
        source_keys = [source]
    else:
        source_keys = list_all_sources(configs, branch=branch)

    if not source_keys:
        print(f"[main] Không có nguồn nào available cho branch={branch}")
        return []

    print(f"[main] Sources by priority: {source_keys}")
    produced = []

    for skey in source_keys:
        if len(produced) >= max_articles:
            break
        try:
            adapter = get_adapter(skey, configs)
            is_tabloid = configs[skey].tabloid

            # Lấy danh sách bài với title để Hot Scorer chấm điểm
            articles_meta = adapter.list_with_titles(limit=20)
            print(f"\n[main] {skey}: tìm thấy {len(articles_meta)} bài")

            # Lọc đã xử lý + chấm điểm (có recency boost theo vị trí)
            candidates = [
                (score_article(m.get("title", ""), position=i), m)
                for i, m in enumerate(articles_meta)
                if not is_url_processed(m["url"])
            ]

            # Với nguồn không phải tabloid: sort theo điểm, loại blacklist
            # Với tabloid: giữ thứ tự gốc (Hot Scorer VI không apply)
            if not is_tabloid:
                candidates = [(s, m) for s, m in candidates if s > -99]
                candidates.sort(key=lambda x: x[0], reverse=True)
                if candidates:
                    top_score, top_meta = candidates[0]
                    print(f"  → Bài hot nhất: \"{top_meta.get('title', '')[:60]}\" (score={top_score})")

            for score, meta in candidates:
                if len(produced) >= max_articles:
                    break
                try:
                    article = adapter.fetch_article(meta["url"])
                    result = process_article(article, is_tabloid, dry_run, no_publish)
                    if result is not None:
                        produced.append(result)
                        break  # Lấy 1 bài tốt nhất mỗi nguồn
                except Exception as e:
                    print(f"  [main] Lỗi xử lý {meta['url']}: {e}")
                    mark_skipped(meta["url"], "exception", skey, str(e))
                    continue

        except Exception as e:
            print(f"[main] Lỗi adapter {skey}: {e}")
            continue

    return produced


def run_text(text: str, dry_run: bool = False, no_publish: bool = False) -> Path | None:
    """Mode B — text thủ công + tìm hình Pexels."""
    print("[main] Mode B: text → tìm hình Pexels...")
    from scripts.image_finder import find_images
    images = find_images(text, n=6)
    if not images:
        print("[main] ⚠ Không tìm được hình từ Pexels. Kiểm tra PEXELS_API_KEY.")

    article = Article(
        title=text[:80],
        body=text,
        images=images,
        url=f"manual_text_{int(time.time())}",
        source_name="manual",
        language="vi",
    )
    return process_article(article, is_tabloid=False, dry_run=dry_run, no_publish=no_publish)


def run_recompose(folder: Path) -> Path:
    """Re-compose video từ folder đã có sẵn frames + audio."""
    script_path = folder / "script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Thiếu script.json trong {folder}")
    data = json.loads(script_path.read_text(encoding="utf-8"))
    scenes = data["scenes"]
    output_mp4 = folder / "video.mp4"
    compose_video(scenes, folder, output_mp4)
    print(f"✓ Re-composed: {output_mp4}")
    return output_mp4


# ───────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────

def main():
    if not _acquire_lock():
        return
    try:
        _main_inner()
    finally:
        _release_lock()


def _main_inner():
    parser = argparse.ArgumentParser(description="Football video agent")
    parser.add_argument("--url", help="URL bài báo cụ thể")
    parser.add_argument("--text", help="Mode B — text thủ công")
    parser.add_argument("--source", help="Chỉ 1 nguồn (bongda/vnexpress/...)")
    parser.add_argument("--branch", choices=["vn", "tabloid"], help="Chỉ 1 nhánh")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ sinh script, không render/voice/video")
    parser.add_argument("--recompose", help="Re-compose video từ folder có sẵn")
    parser.add_argument("--max", type=int, default=1, help="Số bài tối đa khi auto-fetch")
    parser.add_argument("--no-publish", action="store_true", help="Tạo video nhưng không đăng lên mạng xã hội")
    args = parser.parse_args()

    if args.recompose:
        run_recompose(Path(args.recompose))
        return

    if args.url:
        run_url(args.url, dry_run=args.dry_run, no_publish=args.no_publish)
        return

    if args.text:
        run_text(args.text, dry_run=args.dry_run, no_publish=args.no_publish)
        return

    # Auto-fetch
    run_auto_fetch(
        branch=args.branch,
        source=args.source,
        dry_run=args.dry_run,
        max_articles=args.max,
        no_publish=args.no_publish,
    )


if __name__ == "__main__":
    main()
