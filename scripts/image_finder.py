"""
image_finder.py — Tìm hình từ Pexels dựa trên context.

Dùng cho Mode B (--text): khi không có bài báo, Claude sinh keywords
rồi tìm ảnh từ Pexels API.

Cần PEXELS_API_KEY trong .env.
"""

from __future__ import annotations
import os
from pathlib import Path

import requests

PEXELS_URL = "https://api.pexels.com/v1/search"
MIN_SIZE   = 720  # pixel tối thiểu cả width lẫn height


# ───────────────────────────────────────────────────────────
# Pexels search
# ───────────────────────────────────────────────────────────

def _pexels_search(query: str, api_key: str, per_page: int = 5) -> list[str]:
    """Tìm ảnh portrait HD trên Pexels. Trả về list URL."""
    try:
        r = requests.get(
            PEXELS_URL,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": per_page, "orientation": "portrait"},
            timeout=15,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        return [p["src"]["large2x"] for p in photos if p.get("src")]
    except Exception as e:
        print(f"  [Pexels] '{query}': {e}")
        return []


def _ask_gemini_keywords(text: str) -> list[str]:
    """Dùng Gemini sinh 3 keyword tiếng Anh để tìm ảnh."""
    try:
        from google import genai
        from google.genai import types as genai_types
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return ["soccer player", "soccer stadium", "soccer match"]
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Give 3 short English Pexels photo search keywords for this SOCCER (association football) news context. "
                f"Use 'soccer' not 'football' to avoid American football results. "
                f"Return ONLY the keywords, one per line:\n\n{text[:300]}"
            ),
            config=genai_types.GenerateContentConfig(max_output_tokens=60, temperature=0.0),
        )
        lines = [l.strip().strip("- ") for l in resp.text.strip().splitlines() if l.strip()]
        keywords = lines[:3] or ["soccer player", "soccer"]
        if not any("soccer" in kw.lower() for kw in keywords):
            keywords[0] = "soccer " + keywords[0]
        return keywords
    except Exception as e:
        print(f"  [image_finder] Gemini keywords lỗi: {e}")
        return ["soccer player", "soccer stadium"]


# ───────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────

def find_images(text: str, n: int = 6) -> list[str]:
    """
    Tìm n URL ảnh từ Pexels phù hợp với context.

    Args:
        text: tiêu đề / nội dung bài / mô tả context
        n: số ảnh tối đa

    Returns: list URL ảnh (có thể ít hơn n nếu Pexels ít kết quả)
    """
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        print("  [image_finder] Thiếu PEXELS_API_KEY — bỏ qua tìm hình")
        return []

    keywords = _ask_gemini_keywords(text)
    all_images: list[str] = []
    for kw in keywords:
        urls = _pexels_search(kw, api_key, per_page=max(3, n // len(keywords) + 1))
        all_images.extend(urls)
        if len(all_images) >= n:
            break

    return list(dict.fromkeys(all_images))[:n]  # dedup + limit


def download_image(url: str, output: Path) -> bool:
    """Tải 1 hình về, validate kích thước ≥ MIN_SIZE."""
    try:
        resp = requests.get(url, timeout=30, stream=True,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        from PIL import Image
        with Image.open(output) as img:
            if min(img.size) < MIN_SIZE:
                output.unlink(missing_ok=True)
                return False
        return True
    except Exception as e:
        print(f"  [image_finder] Tải hình thất bại: {e}")
        return False


def find_images_for_scenes(scenes: list[dict], text: str, output_dir: Path,
                           max_images: int = 6) -> list[Path]:
    """
    Tìm hình cho từng scene và tải về output_dir/scene_XX.jpg.

    Returns: list path hình đã tải (theo thứ tự scenes, None-safe)
    """
    urls = find_images(text, n=max_images)
    if not urls:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for i, url in enumerate(urls[:len(scenes)]):
        out = output_dir / f"scene_{i+1:02d}.jpg"
        if download_image(url, out):
            downloaded.append(out)
    return downloaded
