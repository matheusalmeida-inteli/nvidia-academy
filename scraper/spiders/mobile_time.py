"""Mobile Time spider — telecom and mobile news."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class MobileTimeSpider(NewsSpider):
    pass


def build() -> MobileTimeSpider:
    return MobileTimeSpider(SOURCES_BY_KEY["mobile_time"])
