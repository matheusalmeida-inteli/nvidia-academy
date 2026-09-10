"""Darwin Startups spider — accelerator and seed funds in South Brazil."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class DarwinSpider(AggregatorSpider):
    """Darwin Startups portfolio.

    Aceleradora com portfólio de startups listado em cards; cada card linka
    para o site/perfil da startup com nome, descrição, estágio e setor.
    """

    CARD_SELECTORS = [
        ".portfolio-card",
        ".startup-card",
        ".investida-card",
        "a[href*='/startup/']",
        "a[href*='/portfolio/']",
        "a[href*='/empresa/']",
        "article.startup",
        ".company-card",
        ".startup-item",
        ".portfolio-item",
    ]


def build() -> DarwinSpider:
    return DarwinSpider(SOURCES_BY_KEY["darwin"])
