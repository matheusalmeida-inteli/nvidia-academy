"""Distrito spider — POC for aggregator scraping.

Distrito (https://distrito.me/) is a Brazilian innovation intelligence platform
that maps startups and tracks corporate innovation. The website is JS-heavy,
so we use Playwright to render pages.
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.sources import SOURCES_BY_KEY
from scraper.models import EstagioEnum
from scraper.pipelines.base_spider import BaseSpider
from scraper.pipelines.html_cleaner import extract_main_text, extract_title


class DistritoSpider(BaseSpider[dict]):
    """Spider for Distrito — extracts startup cards and basic info."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._page_queue: list[str] = list(self.source.seed_urls)

    async def parse_list_page(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        startups: list[dict] = []

        for card in self._find_cards(soup):
            try:
                startup = self._parse_card(card, url)
                if startup and self.mark_seen(startup["site"] or startup["nome"]):
                    startups.append(startup)
                    self._stats["items_found"] += 1
            except Exception as e:
                logger.debug(f"[{self.key}] Card parse error: {e}")

        next_page = self._find_next_page(soup, url)
        if next_page and self.mark_seen(next_page):
            logger.info(f"[{self.key}] Queueing next page: {next_page}")
            self._page_queue.append(next_page)

        return startups

    async def parse_detail_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "lxml")
        title = extract_title(soup) or "Unknown"
        text = extract_main_text(html, url=url)

        return {
            "nome": title.strip(),
            "site": url,
            "descricao_curta": text[:500] if text else None,
            "setor": None,
            "estagio": EstagioEnum.DESCONHECIDO.value,
            "localizacao": None,
            "ano_fundacao": None,
            "tamanho_time": None,
            "fontes_scraping": [self.key],
        }

    def _find_cards(self, soup: BeautifulSoup) -> list:
        """Heuristic — try common card selectors."""
        selectors = [
            "a[href*='/startup/']",
            "a[href*='/empresa/']",
            ".startup-card",
            ".company-card",
            "article.startup",
            "div[data-startup]",
        ]
        for sel in selectors:
            cards = soup.select(sel)
            if cards and len(cards) >= 2:
                return cards
        return soup.select("article, .card, li.startup") or []

    def _parse_card(self, card, base_url: str) -> dict | None:
        from scraper.pipelines.html_cleaner import normalize_url
        link = card.get("href") if card.name == "a" else (
            card.find("a", href=True).get("href") if card.find("a", href=True) else None
        )
        if not link:
            return None
        site = normalize_url(base_url, link)
        if not site:
            return None

        title_tag = card.find(["h2", "h3", "h4", "strong"])
        nome = title_tag.get_text(strip=True) if title_tag else (card.get_text(strip=True) or "")[:80]
        if not nome:
            return None

        desc_tag = card.find(["p", ".description", ".desc"])
        descricao = desc_tag.get_text(strip=True)[:300] if desc_tag else None

        return {
            "nome": nome,
            "site": site,
            "descricao_curta": descricao,
            "setor": None,
            "estagio": EstagioEnum.DESCONHECIDO.value,
            "localizacao": None,
            "ano_fundacao": None,
            "tamanho_time": None,
            "fontes_scraping": [self.key],
        }

    def _find_next_page(self, soup: BeautifulSoup, base_url: str) -> str | None:
        from scraper.pipelines.html_cleaner import normalize_url
        for selector in ["a[rel='next']", "a.next", "a[aria-label*='next' i]", "a[aria-label*='próxima' i]"]:
            tag = soup.select_one(selector)
            if tag and tag.get("href"):
                return normalize_url(base_url, tag["href"])
        return None


def build() -> DistritoSpider:
    return DistritoSpider(SOURCES_BY_KEY["distrito"])
