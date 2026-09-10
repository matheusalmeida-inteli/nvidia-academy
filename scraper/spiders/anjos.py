"""Anjos do Brasil spider — angel investor network invested companies."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class AnjosSpider(AggregatorSpider):
    """Anjos do Brasil — companies invested by member angels.

    Página /investidas/ lista as empresas investidas. Cada card traz nome,
    setor, estágio (semente/série) e localização; links apontam para perfis
    ou sites externos das startups.
    """

    CARD_SELECTORS = [
        ".investida-card",
        ".company-investida",
        ".startup-card",
        "a[href*='/investida/']",
        "a[href*='/empresa/']",
        "a[href*='/startup/']",
        ".company-card",
        ".startup-item",
        ".portfolio-item",
        "li.startup",
    ]


def build() -> AnjosSpider:
    return AnjosSpider(SOURCES_BY_KEY["anjos"])
