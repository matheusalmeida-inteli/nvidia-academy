"""Base spider for news-style sources (articles about startups)."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from loguru import logger

from scraper.pipelines.base_spider import BaseSpider
from scraper.pipelines.html_cleaner import (
    extract_main_text,
    extract_title,
    normalize_url,
    parse_date,
)


class NewsSpider(BaseSpider[dict]):
    """Base spider for news portals that publish articles about startups."""

    ARTICLE_SELECTORS = [
        "article",
        ".article",
        ".post",
        ".news-item",
        ".entry",
        ".news-card",
        "a[href*='/noticia/']",
        "a[href*='/article/']",
        "a[href*='/startup/']",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queued_articles: list[str] = []
        self._collected_articles: list[dict] = []

    def _find_articles(self, soup: BeautifulSoup) -> list:
        for sel in self.ARTICLE_SELECTORS:
            items = soup.select(sel)
            if items and len(items) >= 3:
                return items
        return []

    def _find_pagination(self, soup: BeautifulSoup, base_url: str) -> str | None:
        for selector in [
            "a[rel='next']",
            "a.next",
            "a.pagination-next",
            "a[aria-label*='next' i]",
            "a[aria-label*='próxima' i]",
            ".pagination a:last-child",
            "nav.pagination a:last-child",
            ".load-more",
        ]:
            tag = soup.select_one(selector)
            if tag and tag.get("href"):
                return normalize_url(base_url, tag["href"])
        return None

    def _extract_article(self, article, base_url: str) -> dict | None:
        link = None
        if article.name == "a":
            link = article.get("href")
        else:
            a_tag = article.find("a", href=True)
            if a_tag:
                link = a_tag.get("href")

        if not link:
            return None

        url = normalize_url(base_url, link)
        if not url:
            return None

        title_tag = article.find(["h2", "h3", "h4", ".title", "a[title]"])
        titulo = title_tag.get("title") if title_tag else (
            title_tag.get_text(strip=True) if title_tag else ""
        )

        date_tag = article.find(["time", "span", "p"], class_=lambda c: c and any(
            k in str(c).lower() for k in ["date", "data", "published", "time"]
        ))
        data_str = date_tag.get("datetime") or date_tag.get_text(strip=True) if date_tag else None
        data = parse_date(data_str)

        return {
            "titulo": titulo or "Untitled",
            "url": url,
            "data": data,
        }

    def _find_mentioned_startups(self, text: str) -> list[str]:
        """Heuristic: extract company names that look like startups."""
        patterns = [
            r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?(?:\s+(?:AI|Tech|Solutions|Labs|IO|Data|IA|Systems|Platform))?)\b",
        ]
        candidates = set()
        for pat in patterns:
            for match in re.finditer(pat, text):
                name = match.group(1).strip()
                if len(name) >= 4 and len(name) <= 60:
                    skip = {"OpenAI", "Google", "Meta", "Amazon", "Microsoft", "Apple", "NVIDIA",
                            "Brazil", "Brasil", "Startups", "News", "Article", "Company"}
                    if name not in skip:
                        candidates.add(name)
        return list(candidates)[:5]

    async def parse_list_page(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        articles: list[dict] = []

        for article_tag in self._find_articles(soup):
            try:
                article = self._extract_article(article_tag, url)
                if article and self.mark_seen(article["url"]):
                    # Output as article record (compatible with JSONL exporter)
                    articles.append({
                        "titulo": article["titulo"],
                        "url": article["url"],
                        "data_publicacao": article["data"].isoformat() if article["data"] else None,
                        "data": article["data"].isoformat() if article["data"] else None,
                        "fontes_scraping": [self.key],
                    })
                    self._stats["items_found"] += 1
            except Exception as e:
                logger.debug(f"[{self.key}] article extract: {e}")

        next_url = self._find_pagination(soup, url)
        if next_url and self.mark_seen(next_url):
            self._queued_pages.append(next_url)
            logger.info(f"[{self.key}] pagination: {next_url}")

        return articles

    async def parse_detail_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "lxml")
        titulo = extract_title(soup) or "Untitled"
        conteudo = extract_main_text(html, url=url)

        date_tag = soup.find(["time", "meta"], attrs={"property": "article:published_time"})
        data_str = date_tag.get("content") if date_tag and hasattr(date_tag, "get") else None
        data = parse_date(data_str)

        startups_mentioned = self._find_mentioned_startups(conteudo) if conteudo else []

        return {
            "titulo": titulo.strip(),
            "url": url,
            "conteudo": conteudo[:20_000] if conteudo else "",
            "data": data,
            "startups_mentioned": startups_mentioned,
            "fontes_scraping": [self.key],
        }

    def save_article(self, article: dict) -> None:
        self._collected_articles.append(article)
