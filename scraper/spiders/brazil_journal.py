"""Brazil Journal spider — business/startups news."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class BrazilJournalSpider(NewsSpider):
    pass


def build() -> BrazilJournalSpider:
    return BrazilJournalSpider(SOURCES_BY_KEY["brazil_journal"])
