"""Latitud spider — LatAm VC portfolio via Playwright + domain name extraction.

Latitud uses Framer; startups are rendered as cards with logo images (no text).
Names are extracted from domain names.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.sources import SOURCES_BY_KEY
from scraper.models import EstagioEnum
from scraper.pipelines.base_spider import BaseSpider


def domain_to_name(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    name = domain.removeprefix("www.")
    name = re.sub(r"\.(com|br|ai|io|co|tech|ai\.la)$", "", name, flags=re.IGNORECASE)
    name = name.replace("-", " ").replace("_", " ").strip()
    parts = name.split(".")
    name = parts[0] if parts else domain
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    words = name.title().split()
    return " ".join(w.capitalize() for w in words if w)


class LatitudSpider(BaseSpider[dict]):
    """Spider for Latitud — Playwright-rendered Framer site with logo cards."""

    CARD_SELECTORS = [
        "a[href*='.ai']",
        "a[href*='.com']",
        "a[href*='.io']",
        "a[href*='.co']",
        "a[href*='.br']",
        "[data-framer-name='Card'] a",
        "a[target='_blank']",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def parse_list_page(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        seen_urls: set[str] = set()
        startups: list[dict] = []

        for sel in self.CARD_SELECTORS:
            for a in soup.select(sel):
                href = a.get("href", "")
                if not href.startswith("http"):
                    continue
                if "latitud" in href or "youtube" in href or "linkedin" in href or "instagram" in href:
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Name from domain
                nome = domain_to_name(href)
                if not nome or len(nome) < 2:
                    continue

                if self.mark_seen(href):
                    startups.append({
                        "nome": nome,
                        "site": href,
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

    async def parse_detail_page(self, html: str, url: str) -> None:
        return None


def build() -> LatitudSpider:
    return LatitudSpider(SOURCES_BY_KEY["latitud"])
