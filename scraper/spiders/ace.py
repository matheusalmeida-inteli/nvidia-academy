"""ACE Startups spider — accelerator portfolio (WordPress static)."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class ACESpider(AggregatorSpider):
    """ACE Startups portfolio.

    Lista de startups aceleradas em grid de cards; cada card linka para o
    perfil da startup. WordPress — HTML estático servido direto.
    """

    CARD_SELECTORS = [
        ".portfolio-card",
        ".startup-card",
        ".card-portfolio",
        "a[href*='/portfolio/']",
        "a[href*='/empresa/']",
        "a[href*='/startup/']",
        "a[href*='/company/']",
        "article.post",
        "li.startup",
        ".company-card",
        ".portfolio-item",
    ]


def build() -> ACESpider:
    return ACESpider(SOURCES_BY_KEY["ace"])
