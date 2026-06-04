"""
aljazeera.py — Al Jazeera Sports adapter (tiếng Anh).
"""

from __future__ import annotations
import html as html_mod
import re
from ..base import BaseAdapter, Article


class AlJazeeraAdapter(BaseAdapter):
    """https://www.aljazeera.com/sports"""

    _BASE = "https://www.aljazeera.com"

    def list_latest(self, limit: int = 20) -> list[str]:
        return [m["url"] for m in self.list_with_titles(limit)]

    def list_with_titles(self, limit: int = 20) -> list[dict]:
        html = self._get(self.config.homepage)
        pattern = re.compile(r'href="(/sports/\d{4}/\d{1,2}/\d{1,2}/([^"]{10,150}))"')
        articles: list[dict] = []
        seen: set[str] = set()
        for path, slug in pattern.findall(html):
            url = self._BASE + path
            if url in seen:
                continue
            title = slug.replace("-", " ").title()
            seen.add(url)
            articles.append({"url": url, "title": title})
            if len(articles) >= limit:
                break
        return articles

    def fetch_article(self, url: str) -> Article:
        html = self._get(url)

        # Title
        t = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = html_mod.unescape(re.sub(r'<[^>]+>', '', t.group(1)).strip()) if t else ""

        # Body — paragraphs trong article
        paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        clean: list[str] = []
        for p in paras:
            text = re.sub(r'<[^>]+>', '', p).strip()
            text = html_mod.unescape(text)
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 40:
                clean.append(text)
        body = " ".join(clean[:20])[:4000]

        imgs = self.extract_article_images(html)

        # Fallback Pexels nếu ảnh ít hơn 3
        if len(imgs) < 3:
            try:
                from scripts.image_finder import find_images
                pexels_imgs = find_images(title or "football world cup messi", n=6)
                imgs = imgs + [u for u in pexels_imgs if u not in imgs]
            except Exception:
                pass

        return Article(
            title=title, body=body, images=imgs[:8], url=url,
            source_name="aljazeera", language="en",
        )
