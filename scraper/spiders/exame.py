"""Exame Startups spider — Exame coverage of startup ecosystem."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class ExameSpider(NewsSpider):
    pass


def build() -> ExameSpider:
    return ExameSpider(SOURCES_BY_KEY["exame"])
