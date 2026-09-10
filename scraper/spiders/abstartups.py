"""Abstartups spider — Brazilian Startup Association members."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class AbstartupsSpider(AggregatorSpider):
    """Abstartups associadas.

    Diretório de startups associadas, servido como lista estática. Cada item
    contém nome, setor e localização; muitos cards apontam para o site da
    própria startup (link externo), então o parse mantém o fallback genérico.
    """

    CARD_SELECTORS = [
        ".associada-card",
        ".member-card",
        ".associate-card",
        "li.associada",
        ".startup-card",
        "a[href*='/associada/']",
        "a[href*='/empresa/']",
        "a[href*='/startup/']",
        ".company-card",
        ".startup-item",
        ".portfolio-item",
    ]


def build() -> AbstartupsSpider:
    return AbstartupsSpider(SOURCES_BY_KEY["abstartups"])
