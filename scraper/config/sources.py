"""Source definitions for all 22 TAPI-listed scraping targets."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceCategory(StrEnum):
    """Categorization of TAPI-listed sources."""

    AGGREGATOR = "aggregator"
    INVESTOR_ACCELERATOR = "investor_accelerator"
    NEWS = "news"


class SourceType(StrEnum):
    """How to fetch the source."""

    STATIC = "static"
    DYNAMIC = "dynamic"


@dataclass(frozen=True)
class Source:
    """Definition of a single source to scrape."""

    key: str
    name: str
    base_url: str
    category: SourceCategory
    source_type: SourceType
    description: str
    seed_urls: tuple[str, ...] = ()
    rate_limit_seconds: float = 2.0
    requires_javascript: bool = False
    robots_txt_url: str | None = None
    notes: str = ""
    enabled: bool = True
    priority: int = 5


# === TAPI Section 7.1 — Fontes principais no Brasil ===

PRINCIPAL_SOURCES: tuple[Source, ...] = (
    Source(
        key="startse",
        name="StartSe",
        base_url="https://www.startse.com/",
        category=SourceCategory.NEWS,
        source_type=SourceType.STATIC,
        description="Portal de inovação e startups — articles, news, AI coverage",
        seed_urls=("https://www.startse.com/noticias/",),
        rate_limit_seconds=2.5,
        robots_txt_url="https://www.startse.com/robots.txt",
        priority=4,
        notes="Site pivoted to business education; /startups/ removed. Using /noticias/ instead.",
    ),
    Source(
        key="distrito",
        name="Distrito",
        base_url="https://distrito.me/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.DYNAMIC,
        description="Mapeamento de startups e inovação corporativa no Brasil — pivoted to enterprise AI",
        seed_urls=("https://distrito.me/startups/",),
        rate_limit_seconds=2.0,
        requires_javascript=True,
        robots_txt_url="https://distrito.me/robots.txt",
        priority=3,
        enabled=True,
        notes="Site pivoted to enterprise AI consulting; no longer maintains startup directory",
    ),
    Source(
        key="latitud",
        name="Latitud",
        base_url="https://www.latitud.com/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.DYNAMIC,
        description="Venture capital focada em founders latino-americanos",
        seed_urls=("https://www.latitud.com/portfolio",),
        rate_limit_seconds=2.0,
        requires_javascript=True,
        robots_txt_url="https://www.latitud.com/robots.txt",
        priority=9,
    ),
    Source(
        key="cubo",
        name="Cubo Itaú",
        base_url="https://cubo.itau/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.DYNAMIC,
        description="Hub de inovação do Itaú — startups residentes e alumni",
        seed_urls=("https://cubo.itau/startups",),
        rate_limit_seconds=2.0,
        requires_javascript=True,
        robots_txt_url="https://cubo.network/robots.txt",
        priority=9,
    ),
    Source(
        key="ace",
        name="ACE Startups",
        base_url="https://acestartups.com.br/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.STATIC,
        description="Aceleradora de startups — portfolio de empresas aceleradas",
        seed_urls=("https://acestartups.com.br/portfolio/",),
        rate_limit_seconds=2.0,
        priority=7,
    ),
    Source(
        key="endeavor",
        name="Endeavor Brasil",
        base_url="https://endeavor.org.br/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.STATIC,
        description="Rede de empreendedores de alto impacto — escala e escape velocity",
        seed_urls=("https://endeavor.org.br/empresas/",),
        rate_limit_seconds=2.0,
        requires_javascript=True,
        priority=2,
        enabled=True,
        notes="Cloudflare 403 blocking; needs headless browser",
    ),
    Source(
        key="abstartups",
        name="Abstartups",
        base_url="https://abstartups.com.br/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.STATIC,
        description="Associação Brasileira de Startups — associadas e ecossistema",
        seed_urls=("https://abstartups.com.br/associadas/",),
        rate_limit_seconds=2.0,
        priority=7,
    ),
    Source(
        key="bossa",
        name="Bossa Invest",
        base_url="https://bossainvest.com/",
        category=SourceCategory.INVESTOR_ACCELERATOR,
        source_type=SourceType.STATIC,
        description="Fundo de venture capital — portfolio e investidas",
        seed_urls=("https://bossainvest.com/",),
        rate_limit_seconds=2.0,
        priority=2,
        enabled=True,
        notes="Portfolio page 404; site is mostly institutional without startup list",
    ),
    Source(
        key="anjos",
        name="Anjos do Brasil",
        base_url="https://www.anjosdobrasil.net/",
        category=SourceCategory.INVESTOR_ACCELERATOR,
        source_type=SourceType.STATIC,
        description="Rede de investidores-anjo — startups investidas",
        seed_urls=("https://www.anjosdobrasil.net/investidas/",),
        rate_limit_seconds=2.0,
        priority=5,
    ),
    Source(
        key="darwin",
        name="Darwin Startups",
        base_url="https://www.darwinstartups.com/",
        category=SourceCategory.INVESTOR_ACCELERATOR,
        source_type=SourceType.STATIC,
        description="Aceleradora e fundos de seed no Sul do Brasil",
        seed_urls=("https://www.darwinstartups.com/portfolio/",),
        rate_limit_seconds=2.0,
        priority=5,
    ),
    Source(
        key="liga",
        name="Liga Ventures",
        base_url="https://liga.ventures/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.STATIC,
        description="Corporate venture, open innovation e inteligência de mercado",
        seed_urls=("https://liga.ventures/",),
        rate_limit_seconds=2.0,
        priority=2,
        enabled=True,
        notes="Portfolio page 404; site is mostly content/magazine",
    ),
    Source(
        key="wow",
        name="WOW Aceleradora",
        base_url="https://www.wow.ac/",
        category=SourceCategory.INVESTOR_ACCELERATOR,
        source_type=SourceType.STATIC,
        description="Aceleradora com foco em impacto e inovação — 99+ startups no portfolio",
        seed_urls=("https://www.wow.ac/portfolio",),
        rate_limit_seconds=2.0,
        priority=10,
    ),
    Source(
        key="inovativa",
        name="InovAtiva Brasil",
        base_url="https://www.inovativabrasil.com.br/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.STATIC,
        description="Programa de aceleração do governo federal",
        seed_urls=("https://www.inovativabrasil.com.br/",),
        rate_limit_seconds=2.0,
        priority=2,
        enabled=True,
        notes="Under maintenance; cannot scrape",
    ),
    Source(
        key="open100",
        name="100 Open Startups",
        base_url="https://www.openstartups.net/",
        category=SourceCategory.AGGREGATOR,
        source_type=SourceType.DYNAMIC,
        description="Ranking de startups com soluções para grandes corporações",
        seed_urls=("https://www.openstartups.net/ranking",),
        rate_limit_seconds=2.0,
        requires_javascript=True,
        priority=8,
    ),
)


# === TAPI Section 7.2 — Fontes de notícias e sinais públicos ===

NEWS_SOURCES: tuple[Source, ...] = (
    Source(
        key="brazil_journal",
        name="Brazil Journal",
        base_url="https://braziljournal.com/",
        category=SourceCategory.NEWS,
        source_type=SourceType.STATIC,
        description="Negócios, startups e M&A no Brasil",
        seed_urls=("https://braziljournal.com/",),
        rate_limit_seconds=2.5,
        priority=7,
    ),
    Source(
        key="neofeed",
        name="NeoFeed",
        base_url="https://neofeed.com.br/",
        category=SourceCategory.NEWS,
        source_type=SourceType.STATIC,
        description="Jornalismo de negócios, tecnologia e startups",
        seed_urls=("https://neofeed.com.br/",),
        rate_limit_seconds=2.5,
        priority=7,
    ),
    Source(
        key="exame",
        name="Exame Startups",
        base_url="https://exame.com/bussola/startups/",
        category=SourceCategory.NEWS,
        source_type=SourceType.DYNAMIC,
        description="Cobertura da Exame sobre o ecossistema de startups",
        seed_urls=("https://exame.com/bussola/startups/",),
        rate_limit_seconds=2.5,
        requires_javascript=True,
        priority=6,
    ),
    Source(
        key="startups_com_br",
        name="Startups.com.br",
        base_url="https://startups.com.br/",
        category=SourceCategory.NEWS,
        source_type=SourceType.STATIC,
        description="Portal brasileiro de notícias sobre startups",
        seed_urls=("https://startups.com.br/",),
        rate_limit_seconds=2.0,
        priority=5,
    ),
    Source(
        key="pegn",
        name="Pequenas Empresas & Grandes Negócios",
        base_url="https://revistapegn.globo.com/",
        category=SourceCategory.NEWS,
        source_type=SourceType.DYNAMIC,
        description="Revista da Globo sobre pequenos negócios e startups",
        seed_urls=("https://revistapegn.globo.com/Startups/",),
        rate_limit_seconds=2.5,
        requires_javascript=True,
        priority=5,
    ),
    Source(
        key="valor",
        name="Valor Econômico",
        base_url="https://valor.globo.com/",
        category=SourceCategory.NEWS,
        source_type=SourceType.DYNAMIC,
        description="Jornal de economia, negócios e finanças",
        seed_urls=("https://valor.globo.com/startups/",),
        rate_limit_seconds=2.5,
        requires_javascript=True,
        priority=5,
    ),
    Source(
        key="meio_mensagem",
        name="Meio & Mensagem",
        base_url="https://www.meioemensagem.com.br/",
        category=SourceCategory.NEWS,
        source_type=SourceType.STATIC,
        description="Mídia, marketing, comunicação e tecnologia",
        seed_urls=("https://www.meioemensagem.com.br/",),
        rate_limit_seconds=2.0,
        priority=3,
    ),
    Source(
        key="mobile_time",
        name="Mobile Time",
        base_url="https://www.mobiletime.com.br/",
        category=SourceCategory.NEWS,
        source_type=SourceType.STATIC,
        description="Notícias sobre telecom, mobile e tecnologia",
        seed_urls=("https://www.mobiletime.com.br/",),
        rate_limit_seconds=2.0,
        priority=3,
    ),
)


ALL_SOURCES: tuple[Source, ...] = PRINCIPAL_SOURCES + NEWS_SOURCES

SOURCES_BY_KEY: dict[str, Source] = {s.key: s for s in ALL_SOURCES}


def get_enabled_sources() -> list[Source]:
    """Return all enabled sources, sorted by priority descending."""
    return sorted([s for s in ALL_SOURCES if s.enabled], key=lambda s: -s.priority)


def get_sources_by_category(category: SourceCategory) -> list[Source]:
    return [s for s in ALL_SOURCES if s.category == category and s.enabled]
