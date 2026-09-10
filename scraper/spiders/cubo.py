"""Cubo Itaú spider — innovation hub startups."""
from __future__ import annotations

from scraper.config.sources import SOURCES_BY_KEY
from scraper.spiders._base_aggregator import AggregatorSpider


class CuboSpider(AggregatorSpider):
    """Cubo Itaú startup directory (JS-rendered hub).

    Cards link to `/startups/<slug>` or `/startup/<slug>`. Por ser uma SPA,
    a fonte usa Playwright, mas o parse é idêntico: cards com título, descrição,
    setor e estágio.
    """

    CARD_SELECTORS = [
        "a[href*='/startups/']",
        "a[href*='/startup/']",
        "a[href*='/negocio/']",
        "a[href*='/empresa/']",
        ".startup-card",
        ".card-startup",
        "div[data-startup]",
        "article.startup",
        "a[href*='/company/']",
        ".startup-item",
        ".portfolio-item",
    ]


def build() -> CuboSpider:
    return CuboSpider(SOURCES_BY_KEY["cubo"])
