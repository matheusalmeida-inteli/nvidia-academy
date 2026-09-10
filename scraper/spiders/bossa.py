"""Bossa Invest spider — venture capital portfolio."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class BossaSpider(AggregatorSpider):
    pass


def build() -> BossaSpider:
    return BossaSpider(SOURCES_BY_KEY["bossa"])
