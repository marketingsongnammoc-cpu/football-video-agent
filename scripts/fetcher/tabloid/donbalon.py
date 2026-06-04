"""
Don Balon adapter — STUB.
"""
from __future__ import annotations
import re
from html import unescape
from ..base import BaseAdapter, Article


class DonBalonAdapter(BaseAdapter):
    def list_latest(self, limit: int = 20) -> list[str]:
        html = self._get(self.config.homepage)
        pattern = re.compile(r"href=\"(https?://(?:www\.)?donbalon.com/[^\"#?]+)\"", re.IGNORECASE)
        urls, seen = [], set()
        for m in pattern.finditer(html):
            u = m.group(1)
            if u in seen or u == self.config.homepage:
                continue
            seen.add(u)
            urls.append(u)
            if len(urls) >= limit:
                break
        return urls

    def fetch_article(self, url: str) -> Article:
        html = self._get(url)
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip() if title_m else ""
        body_paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
        body = "\n\n".join(unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in body_paragraphs if len(re.sub(r"<[^>]+>", "", p).strip()) > 20)
        images = self.extract_article_images(html)
        return Article(
            title=title, body=body, images=images, url=url,
            source_name="Don Balon", language="es",
        )
