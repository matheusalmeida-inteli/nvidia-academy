"""Valor Econômico spider — financial journalism."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class ValorSpider(NewsSpider):
    pass


def build() -> ValorSpider:
    return ValorSpider(SOURCES_BY_KEY["valor"])
