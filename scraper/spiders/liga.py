"""Liga Ventures spider — corporate venture and open innovation."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class LigaSpider(AggregatorSpider):
    pass


def build() -> LigaSpider:
    return LigaSpider(SOURCES_BY_KEY["liga"])
