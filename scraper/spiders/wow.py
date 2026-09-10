"""WOW Aceleradora spider — extracts startups from portfolio page.

WOW pattern: each card has a name heading followed by a link "Acessar o site da Startup".
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.sources import SOURCES_BY_KEY
from scraper.models import EstagioEnum
from scraper.pipelines.base_spider import BaseSpider


class WOWSpider(BaseSpider[dict]):
    """Spider for WOW Aceleradora — uses card structure with 'Acessar o site' link."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._extracted_pairs: list[tuple[str, str]] = []

    def _extract_pairs(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Walk the DOM and find (startup_name, startup_url) pairs."""
        pairs: list[tuple[str, str]] = []
        seen_sites: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if "Acessar o site" not in text:
                continue
            if not href.startswith("http"):
                continue
            if "wow.ac" in href:
                continue
            if href in seen_sites:
                continue
            seen_sites.add(href)

            name = self._find_name_near(a)
            if name and 2 < len(name) < 60:
                pairs.append((name, href))

        return pairs

    def _find_name_near(self, anchor) -> str | None:
        """Look for the startup name near an 'Acessar o site' anchor."""
        for heading in anchor.find_all_previous(["h1", "h2", "h3", "h4", "h5", "strong", "span"]):
            text = heading.get_text(strip=True)
            if text and 2 < len(text) < 60 and text != anchor.get_text(strip=True):
                skip = {"Acessar o site da Startup", "Conheça as Startups", "Portfólio", "WOW"}
                if text not in skip:
                    return text
        return None

    async def parse_list_page(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        pairs = self._extract_pairs(soup)
        startups: list[dict] = []
        for name, site in pairs:
            if not self.mark_seen(site):
                continue
            startups.append({
                "nome": name,
                "site": site,
                "descricao_curta": None,
                "setor": None,
                "estagio": EstagioEnum.DESCONHECIDO.value,
                "localizacao": None,
                "ano_fundacao": None,
                "tamanho_time": None,
                "fontes_scraping": [self.key],
            })
            self._stats["items_found"] += 1
        logger.info(f"[{self.key}] Extracted {len(startups)} startups from {url}")
        return startups

    async def parse_detail_page(self, html: str, url: str) -> dict | None:
        return None


def build() -> WOWSpider:
    return WOWSpider(SOURCES_BY_KEY["wow"])
