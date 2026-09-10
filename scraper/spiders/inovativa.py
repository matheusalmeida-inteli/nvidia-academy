"""InovAtiva Brasil spider — federal acceleration program."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class InovativaSpider(AggregatorSpider):
    pass


def build() -> InovativaSpider:
    return InovativaSpider(SOURCES_BY_KEY["inovativa"])
