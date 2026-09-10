"""Meio & Mensagem spider — media/marketing news."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_news import NewsSpider


class MeioMensagemSpider(NewsSpider):
    pass


def build() -> MeioMensagemSpider:
    return MeioMensagemSpider(SOURCES_BY_KEY["meio_mensagem"])
