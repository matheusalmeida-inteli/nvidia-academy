"""Endeavor Brasil spider — high-impact entrepreneurs network."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class EndeavorSpider(AggregatorSpider):
    pass


def build() -> EndeavorSpider:
    return EndeavorSpider(SOURCES_BY_KEY["endeavor"])
