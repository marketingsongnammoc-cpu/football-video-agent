"""
Tuổi Trẻ Thể Thao adapter.
"""

from __future__ import annotations
import re
from html import unescape
from ..base import BaseAdapter, Article


class TuoiTreAdapter(BaseAdapter):
    """https://tuoitre.vn/the-thao/bong-da.htm"""

    def list_latest(self, limit: int = 20) -> list[str]:
        html = self._get(self.config.homepage)
        # Tuổi Trẻ: link bài kết thúc bằng .htm
        pattern = re.compile(
            r'href="(/the-thao/[^"]+\d{15,}\.htm)"',
            re.IGNORECASE,
        )
        urls = []
        seen = set()
        for m in pattern.finditer(html):
            path = m.group(1)
            url = "https://tuoitre.vn" + path
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= limit:
                break
        return urls

    def fetch_article(self, url: str) -> Article:
        html = self._get(url)

        # Title
        title_m = re.search(r'<h1[^>]*class="[^"]*detail-title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
        if not title_m:
            title_m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""

        # Body
        body_paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)
        body = "\n\n".join(
            unescape(re.sub(r"<[^>]+>", "", p)).strip()
            for p in body_paragraphs
            if len(re.sub(r"<[^>]+>", "", p).strip()) > 20
        )

        images = self.extract_article_images(html)

        return Article(
            title=title,
            body=body,
            images=images,
            url=url,
            source_name="Tuổi Trẻ",
            language="vi",
        )
