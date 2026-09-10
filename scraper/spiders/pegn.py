"""PEGN (Pequenas Empresas & Grandes Negócios) spider."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class PegnSpider(NewsSpider):
    pass


def build() -> PegnSpider:
    return PegnSpider(SOURCES_BY_KEY["pegn"])
