"""
Bóng Đá Plus adapter — bongdaplus.vn
"""

from __future__ import annotations
import re
from html import unescape
from ..base import BaseAdapter, Article


class BongDaPlusAdapter(BaseAdapter):
    """https://bongdaplus.vn"""

    _URL_PATTERN = re.compile(
        r'href="(https?://(?:www\.)?bongdaplus\.vn/[^"#?]{10,200})"',
        re.IGNORECASE,
    )
    _LINK_PATTERN = re.compile(
        r'href="(https?://(?:www\.)?bongdaplus\.vn/[^"#?]{10,200})"[^>]*>'
        r'\s*([^<]{5,150})\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    _SKIP_CONTENT = [
        "Bản quyền thuộc", "Giấy phép số", "Tổng biên tập",
        "Địa chỉ:", "Điện thoại:", "© 20", "All rights reserved",
    ]

    # ─── Listing ─────────────────────────────────────────────

    def list_latest(self, limit: int = 20) -> list[str]:
        return [m["url"] for m in self.list_with_titles(limit)]

    def list_with_titles(self, limit: int = 20) -> list[dict]:
        html = self._get(self.config.homepage)
        articles: list[dict] = []
        seen: set[str] = set()

        for m in self._LINK_PATTERN.finditer(html):
            url   = m.group(1)
            title = re.sub(r'\s+', ' ', unescape(m.group(2))).strip()
            if url in seen or url == self.config.homepage:
                continue
            if not title or len(title) < 8:
                continue
            if "bongdaplus.vn" not in url:
                continue
            seen.add(url)
            articles.append({"url": url, "title": title})
            if len(articles) >= limit:
                break

        if not articles:
            for m in self._URL_PATTERN.finditer(html):
                url = m.group(1)
                if url not in seen and url != self.config.homepage:
                    seen.add(url)
                    articles.append({"url": url, "title": ""})
                    if len(articles) >= limit:
                        break

        return articles

    # ─── Fetch article ────────────────────────────────────────

    def fetch_article(self, url: str) -> Article:
        html = self._get(url)

        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""

        paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        clean: list[str] = []
        for p in paras:
            text = unescape(re.sub(r"<[^>]+>", "", p)).strip()
            text = re.sub(r'\s+', ' ', text)
            if len(text) < 20:
                continue
            if any(s in text for s in self._SKIP_CONTENT):
                continue
            clean.append(text)
        body = "\n\n".join(clean[:20])

        images = self.extract_article_images(html)

        return Article(
            title=title, body=body, images=images, url=url,
            source_name="Bóng Đá Plus", language="vi",
        )
