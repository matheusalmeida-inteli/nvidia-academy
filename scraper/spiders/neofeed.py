"""NeoFeed spider — business journalism."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class NeoFeedSpider(NewsSpider):
    pass


def build() -> NeoFeedSpider:
    return NeoFeedSpider(SOURCES_BY_KEY["neofeed"])
