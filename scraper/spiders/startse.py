"""StartSe spider — innovation and AI startup news portal."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class StartSeSpider(NewsSpider):
    pass


def build() -> StartSeSpider:
    return StartSeSpider(SOURCES_BY_KEY["startse"])
