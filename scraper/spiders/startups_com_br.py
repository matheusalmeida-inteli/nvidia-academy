"""Startups.com.br spider — Brazilian startup news portal."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class StartupsComBrSpider(NewsSpider):
    pass


def build() -> StartupsComBrSpider:
    return StartupsComBrSpider(SOURCES_BY_KEY["startups_com_br"])
