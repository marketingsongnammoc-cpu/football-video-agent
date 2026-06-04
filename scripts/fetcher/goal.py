"""
goal.com adapter — nguồn bóng đá quốc tế tiếng Anh.
"""

from __future__ import annotations
import html as html_mod
import re
from .base import BaseAdapter, Article


class GoalAdapter(BaseAdapter):
    """https://www.goal.com/en/news"""

    _SKIP_TITLE = ["quiz", "predict", "best xi", "fantasy", "history of", "all you need"]

    # ─── Listing ─────────────────────────────────────────────

    def list_latest(self, limit: int = 20) -> list[str]:
        return [m["url"] for m in self.list_with_titles(limit)]

    def list_with_titles(self, limit: int = 20) -> list[dict]:
        html = self._get(self.config.homepage)
        pattern = re.compile(r'href="(/en/(?:lists|news)/([^"]{10,120}))"')
        articles: list[dict] = []
        seen: set[str] = set()

        for path, slug in pattern.findall(html):
            url   = "https://www.goal.com" + path
            title = slug.split("/")[0].replace("-", " ").title()
            if url in seen:
                continue
            if any(kw in title.lower() for kw in self._SKIP_TITLE):
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
        t = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title = html_mod.unescape(t.group(1).strip()) if t else ""

        # Body
        paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        clean: list[str] = []
        for p in paras:
            text = re.sub(r'<[^>]+>', '', p).strip()
            text = html_mod.unescape(text)
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 40 and not any(s in text for s in ["Add GOAL.com", "Getty Images Sport"]):
                clean.append(text)
        body = " ".join(clean[:15])[:4000]

        # Images
        images = self.extract_article_images(html)

        # Fallback Pexels nếu không tìm được ảnh
        if not images:
            try:
                from scripts.image_finder import find_images
                images = find_images(title, n=3)
            except Exception:
                pass

        return Article(
            title=title, body=body, images=images, url=url,
            source_name="goal.com", language="en",
        )
