"""
fetcher/base.py — Base adapter interface cho tất cả nguồn báo.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re
import hashlib
import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# Regex blacklist chung cho ảnh
IMAGE_BLACKLIST_RE = re.compile(
    r"(banner|logo|sponsor|ads?|advertising|icon|placeholder|default|favicon|google_news|qrcode)",
    re.IGNORECASE,
)

# Markers đánh dấu đầu phần "bài liên quan" — cắt HTML tại đây
_RELATED_CUT_MARKERS = [
    # English
    'id="related', 'class="related', 'id="recommended', 'class="recommended',
    '"relatedArticles"', '"related_articles"', 'data-module="related"',
    'class="taboola', 'class="outbrain', 'YOU MAY ALSO LIKE',
    'More Stories', 'Read Next', 'See Also', 'Also Read', 'READ MORE:',
    # Vietnamese
    'Tin liên quan', 'tin-lien-quan', 'related-news', 'box-related',
    'BÀI VIẾT LIÊN QUAN', 'Xem thêm:', 'Đọc thêm:',
    'box_tin_lq', 'id="box-related', 'class="box-news-related',
]

# Patterns container body bài viết (thử theo thứ tự)
_ARTICLE_BODY_PATTERNS = [
    r'<article\b[^>]*>([\s\S]+?)</article>',
    r'<div[^>]+\bclass="[^"]*\b(?:article|post|entry)[-_](?:body|content|text)\b[^"]*"[^>]*>([\s\S]+?)</div>',
    r'<div[^>]+\bclass="[^"]*\bcontentDetail\b[^"]*"[^>]*>([\s\S]+?)</div>',
    r'<div[^>]+\bclass="[^"]*\bdetailContent\b[^"]*"[^>]*>([\s\S]+?)</div>',
    r'<div[^>]+\bclass="[^"]*\bnews[-_]?body\b[^"]*"[^>]*>([\s\S]+?)</div>',
    r'<div[^>]+\bclass="[^"]*\bsingle[-_]?content\b[^"]*"[^>]*>([\s\S]+?)</div>',
    r'<div[^>]+\bid="[^"]*\b(?:article|content|detail)[-_](?:body|content|text)\b[^"]*"[^>]*>([\s\S]+?)</div>',
]

# Regex lấy URL ảnh từ các attribute phổ biến
_IMG_ATTRS_PAT = re.compile(
    r'(?:src|data-src|data-original|data-lazy-src|content)='
    r'"(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))(?:[?#][^"]*)?',
    re.IGNORECASE,
)


@dataclass
class Article:
    title: str
    body: str
    images: list[str]
    url: str
    source_name: str
    language: str = "vi"
    published_at: Optional[str] = None


@dataclass
class FetchConfig:
    name: str
    branch: str  # 'vn' | 'tabloid'
    homepage: str
    language: str
    tabloid: bool
    image_cdn_whitelist: list[str]
    priority: int = 99


class BaseAdapter(ABC):
    """Mọi nguồn báo kế thừa class này."""

    def __init__(self, config: FetchConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    @abstractmethod
    def list_latest(self, limit: int = 20) -> list[str]:
        """Trả về list URL bài mới nhất từ homepage."""

    @abstractmethod
    def fetch_article(self, url: str) -> Article:
        """Fetch chi tiết 1 bài."""

    # ─── Helpers ───

    def _get(self, url: str, timeout: int = 15) -> str:
        """GET HTML với headers chuẩn."""
        resp = self.session.get(url, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def extract_article_images(self, html: str, max_images: int = 6) -> list[str]:
        """
        Lấy ảnh liên quan đến bài viết theo 3 bước ưu tiên:
          1. og:image / twitter:image — ảnh featured do ban biên tập chọn, luôn đúng chủ đề
          2. Ảnh trong article body container (sau khi cắt bỏ phần related/recommended)
          3. Fallback: full-page scan đã cắt related

        Khác với filter_images(): og:image không cần qua CDN whitelist.
        """
        images: list[str] = []
        seen: set[str] = set()
        cdn_wl = self.config.image_cdn_whitelist

        def _accept(u: str, require_cdn: bool = True) -> bool:
            u = u.strip()
            if not u or u in seen:
                return False
            if IMAGE_BLACKLIST_RE.search(u):
                return False
            if require_cdn and cdn_wl and not any(cdn in u for cdn in cdn_wl):
                return False
            seen.add(u)
            images.append(u)
            return True

        # ── 1. og:image / twitter:image ─────────────────────
        for pat in [
            r'property="og:image"\s+content="([^"]+)"',
            r'content="([^"]+)"\s+property="og:image"',
            r'name="twitter:image"\s+content="([^"]+)"',
            r'content="([^"]+)"\s+name="twitter:image"',
        ]:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                _accept(m.group(1), require_cdn=False)
                break

        if len(images) >= max_images:
            return images

        # ── 2. Cắt HTML tại related/recommended markers ─────
        trimmed = html
        html_lower = html.lower()
        for marker in _RELATED_CUT_MARKERS:
            idx = html_lower.find(marker.lower())
            # Chỉ cắt nếu marker xuất hiện sau ít nhất 25% trang (tránh cắt header)
            if idx > len(html) // 4:
                trimmed = html[:idx]
                break

        # ── 3. Tìm trong article body container ─────────────
        search_scope = trimmed
        for pat in _ARTICLE_BODY_PATTERNS:
            m = re.search(pat, trimmed, re.IGNORECASE | re.DOTALL)
            if m and len(m.group(1)) > 300:
                search_scope = m.group(1)
                break

        # Extract ảnh từ scope
        for m in _IMG_ATTRS_PAT.finditer(search_scope):
            _accept(m.group(1), require_cdn=True)
            if len(images) >= max_images:
                break

        return images

    def filter_images(self, urls: list[str], max_images: int | None = None) -> list[str]:
        """
        Filter chung: whitelist CDN + blacklist regex + unique.
        max_images=None nghĩa là không giới hạn (lấy hết).
        """
        seen = set()
        out = []
        for u in urls:
            if not u or u in seen:
                continue
            seen.add(u)
            # Check whitelist CDN
            if not any(cdn in u for cdn in self.config.image_cdn_whitelist):
                continue
            # Check blacklist
            if IMAGE_BLACKLIST_RE.search(u):
                continue
            out.append(u)
            if max_images is not None and len(out) >= max_images:
                break
        return out

    def download_image(self, url: str, output: Path) -> bool:
        """Download 1 image. Trả về True nếu OK + đủ kích thước."""
        try:
            resp = self.session.get(url, timeout=30, stream=True)
            resp.raise_for_status()
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            # Verify size — accept nếu bất kỳ chiều nào >= 600px
            from PIL import Image as PILImage
            with PILImage.open(output) as img:
                w, h = img.size
                if max(w, h) < 600:
                    output.unlink(missing_ok=True)
                    return False
            return True
        except Exception as e:
            print(f"  [download_image] fail {url}: {e}")
            return False

    def list_with_titles(self, limit: int = 20) -> list[dict]:
        """
        Trả về [{url, title}] để Hot Scorer có thể chấm điểm trước khi fetch.
        Mặc định: wrap list_latest() với title="".
        Override trong adapter để trả về title thật từ homepage.
        """
        return [{"url": u, "title": ""} for u in self.list_latest(limit)]

    @staticmethod
    def article_hash(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:12]
