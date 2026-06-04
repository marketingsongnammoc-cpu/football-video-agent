"""
Bongda.com.vn adapter.
"""

from __future__ import annotations
import re
from html import unescape
from ..base import BaseAdapter, Article


class BongdaAdapter(BaseAdapter):
    """https://bongda.com.vn"""

    # bongda.com.vn nhúng bài viết trong JSON-LD structured data
    _JSON_ITEM_PAT = re.compile(
        r'"url"\s*:\s*"(https://bongda\.com\.vn/[^"]{10,200}\.html)"'
        r'.*?"name"\s*:\s*"([^"]{5,200})"',
        re.DOTALL,
    )
    _SKIP_CONTENT = [
        "Giấy phép số", "Tổng biên tập", "Phó tổng biên tập",
        "Địa chỉ:", "Điện thoại:", "Fax:", "Email:", "VPĐD",
        "Bản quyền thuộc", "Mọi thông tin",
    ]
    _SKIP_JS = [
        "function ", "const ", "var ", "let ", "document.", "getElementById",
        "querySelector", "window.", "=>", "console.", ".innerHTML", ".style.",
    ]

    # ─── Listing ─────────────────────────────────────────────

    def list_latest(self, limit: int = 20) -> list[str]:
        return [m["url"] for m in self.list_with_titles(limit)]

    def list_with_titles(self, limit: int = 20) -> list[dict]:
        """Trả về [{url, title}] từ JSON-LD trên homepage."""
        html = self._get(self.config.homepage + "/tin-moi-nhat/")
        articles: list[dict] = []
        seen: set[str] = set()

        for m in self._JSON_ITEM_PAT.finditer(html):
            url   = m.group(1)
            title = unescape(m.group(2).replace("\\u0022", '"')).strip()
            if url in seen:
                continue
            seen.add(url)
            articles.append({"url": url, "title": title})
            if len(articles) >= limit:
                break

        return articles

    # ─── Fetch article ────────────────────────────────────────

    def fetch_article(self, url: str) -> Article:
        html = self._get(url)

        # Title
        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""

        # Body — lọc JS và footer
        paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        clean: list[str] = []
        for p in paras:
            text = unescape(re.sub(r"<[^>]+>", "", p)).strip()
            text = re.sub(r'\s+', ' ', text)
            if len(text) < 20:
                continue
            if any(s in text for s in self._SKIP_CONTENT):
                continue
            if any(js in text for js in self._SKIP_JS):
                continue
            clean.append(text)
        body = "\n\n".join(clean[:20])

        # Images — chỉ lấy hình trong BODY bài viết (không lấy og:image thumbnail)
        images: list[str] = []
        seen: set[str] = set()

        def _add(u: str) -> None:
            u = u.strip()
            if u and u not in seen:
                seen.add(u)
                images.append(u)

        # 1. Ảnh trong article content (figure > img trong contentDetail)
        content_m = re.search(r'class="contentDetail"[^>]*>([\s\S]*?)(?:</article>|<div class="[^"]*related)', html, re.IGNORECASE)
        if content_m:
            content_html = content_m.group(1)
            for m in re.finditer(r'(?:src|data-src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp|JPG))"', content_html, re.IGNORECASE):
                _add(m.group(1))

        # 2. Fallback: /news/editor/ URLs trong toàn bộ HTML nếu chưa đủ
        if len(images) < 3:
            for m in re.finditer(r'"(https?://[^"]+/news/editor/[^"]+\.(?:jpg|jpeg|png|webp|JPG))"', html, re.IGNORECASE):
                _add(m.group(1))

        return Article(
            title=title, body=body, images=images, url=url,
            source_name="Bóng Đá", language="vi",
        )
