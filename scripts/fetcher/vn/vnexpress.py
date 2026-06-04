"""
VnExpress Thể Thao adapter.
"""

from __future__ import annotations
import re
from html import unescape
from ..base import BaseAdapter, Article


class VnExpressAdapter(BaseAdapter):
    """https://vnexpress.net/the-thao/bong-da"""

    def list_latest(self, limit: int = 20) -> list[str]:
        return [m["url"] for m in self.list_with_titles(limit)]

    def list_with_titles(self, limit: int = 20) -> list[dict]:
        html = self._get(self.config.homepage)
        # VnExpress: link bài dạng vnexpress.net/tieu-de-XXXXXXX.html
        # Homepage bongda nên tất cả link đều là bài bóng đá
        pattern = re.compile(
            r'href="(https://vnexpress\.net/[^"#?]+\d{7,}\.html)"[^>]*>\s*([^<]{5,150})',
            re.IGNORECASE,
        )
        articles = []
        seen = set()
        for m in pattern.finditer(html):
            u = m.group(1)
            if u in seen or "#box_comment" in u:
                continue
            seen.add(u)
            title = unescape(m.group(2).strip())
            articles.append({"url": u, "title": title})
            if len(articles) >= limit:
                break
        return articles

    def fetch_article(self, url: str) -> Article:
        html = self._get(url)

        # Title
        title_m = re.search(r'<h1[^>]*class="title-detail"[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
        if not title_m:
            title_m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""

        # Body: lấy <p class="Normal"> hoặc <p> trong article
        body_paragraphs = re.findall(
            r'<p[^>]*class="Normal"[^>]*>(.*?)</p>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if not body_paragraphs:
            body_paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)
        body = "\n\n".join(
            unescape(re.sub(r"<[^>]+>", "", p)).strip()
            for p in body_paragraphs
        )

        # Images — chỉ lấy hình trong BODY bài viết (không lấy og:image thumbnail)
        images: list[str] = []
        seen: set[str] = set()

        def _add(u: str) -> None:
            u = u.strip()
            if u and u not in seen and any(cdn in u for cdn in self.config.image_cdn_whitelist):
                seen.add(u)
                images.append(u)

        # 1. <meta itemprop="url" content="..."> — ảnh trong body bài viết
        for m in re.finditer(r'itemprop="url"\s+content="(https://[^"]+vnecdn[^"]+)"', html):
            u = m.group(1)
            # Bỏ thumbnail nhỏ (w=680, w=460...), chỉ lấy full-size
            if 'w=0' in u or 'w=1200' in u or ('w=' not in u):
                _add(u)

        # 2. <source data-srcset="URL 1x, URL 1.5x"> — ảnh responsive trong body
        for m in re.finditer(r'data-srcset="([^"]+)"', html):
            first_url = m.group(1).split(' ')[0].strip()
            if 'vnecdn.net' in first_url:
                _add(first_url)

        return Article(
            title=title,
            body=body,
            images=images,
            url=url,
            source_name="VnExpress",
            language="vi",
        )
