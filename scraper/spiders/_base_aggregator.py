"""Base spider for aggregator-style sources (startup lists, portfolio pages)."""
from __future__ import annotations

from bs4 import BeautifulSoup
from loguru import logger

from scraper.models import EstagioEnum
from scraper.pipelines.base_spider import BaseSpider
from scraper.pipelines.html_cleaner import extract_main_text, extract_title, normalize_url


def parse_estagio(text: str | None) -> str:
    if not text:
        return EstagioEnum.DESCONHECIDO.value
    t = text.lower()
    if "pre-seed" in t or "pre seed" in t:
        return EstagioEnum.PRE_SEED.value
    if "seed" in t:
        return EstagioEnum.SEED.value
    if "série a" in t or "serie a" in t or "series a" in t:
        return EstagioEnum.SERIE_A.value
    if "série b" in t or "serie b" in t or "series b" in t:
        return EstagioEnum.SERIE_B.value
    if "série c" in t or "serie c" in t or "series c" in t:
        return EstagioEnum.SERIE_C.value
    if "série d" in t or "serie d" in t or "series d" in t:
        return EstagioEnum.SERIE_D.value
    if any(k in t for k in ["série", "serie", "late"]):
        return EstagioEnum.SERIE_LATER.value
    return EstagioEnum.DESCONHECIDO.value


class AggregatorSpider(BaseSpider[dict]):
    """Base spider for aggregator/portfolio pages that list startup cards."""

    CARD_SELECTORS = [
        "a[href*='/startup/']",
        "a[href*='/company/']",
        "a[href*='/empresa/']",
        "a[href*='/portfolio/']",
        ".startup-card",
        ".company-card",
        ".card-startup",
        "article.startup",
        "div[data-startup]",
        "li.startup",
        ".startup-item",
        ".portfolio-item",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queued_pages: list[str] = []

    def _find_cards(self, soup: BeautifulSoup) -> list:
        for sel in self.CARD_SELECTORS:
            cards = soup.select(sel)
            if cards and len(cards) >= 2:
                return cards
        return []

    def _find_links(self, soup: BeautifulSoup, base_url: str, selector: str = "a[href]") -> list[str]:
        links: list[str] = []
        for tag in soup.select(selector):
            href = tag.get("href")
            if href:
                resolved = normalize_url(base_url, href)
                if resolved:
                    links.append(resolved)
        return links

    def _find_pagination(self, soup: BeautifulSoup, base_url: str) -> str | None:
        for selector in [
            "a[rel='next']",
            "a.next",
            "a.pagination-next",
            "a[aria-label*='next' i]",
            "a[aria-label*='próxima' i]",
            "a[aria-label*='seguinte' i]",
            "button[data-page*='next']",
            ".pagination a:last-child",
            ".pagination .next",
            "ul.pagination li:last-child a",
            "nav.pagination a[href*='page']",
        ]:
            tag = soup.select_one(selector)
            if tag and tag.get("href"):
                return normalize_url(base_url, tag["href"])
        return None

    def _parse_card(self, card, base_url: str) -> dict | None:
        link = None
        if card.name == "a":
            link = card.get("href")
        else:
            a_tag = card.find("a", href=True)
            if a_tag:
                link = a_tag.get("href")

        if not link:
            return None

        site = normalize_url(base_url, link)
        if not site:
            return None

        for skip in ["/tag/", "/category/", "/author/", "/page/", "#"]:
            if skip in site:
                return None

        title_tag = card.find(["h2", "h3", "h4", "strong", ".title", ".name"])
        nome = title_tag.get_text(strip=True) if title_tag else ""
        if not nome:
            all_text = card.get_text(separator=" ", strip=True)
            nome = all_text[:80] if all_text else ""
        if not nome:
            return None

        desc_tag = card.find(["p", ".description", ".desc", ".excerpt", ".resume"])
        descricao = desc_tag.get_text(strip=True)[:500] if desc_tag else None

        setor_tag = card.find(["span", "p", "div"], class_=lambda c: c and any(
            k in str(c).lower() for k in ["sector", "setor", "vertical", "area"]
        ))
        setor = setor_tag.get_text(strip=True) if setor_tag else None

        estagio_tag = card.find(["span", "p", "div"], class_=lambda c: c and any(
            k in str(c).lower() for k in ["stage", "estagio", "fase", "round", "serie"]
        ))
        estagio = parse_estagio(estagio_tag.get_text(strip=True) if estagio_tag else None)

        local_tag = card.find(["span", "p", "div"], class_=lambda c: c and any(
            k in str(c).lower() for k in ["location", "local", "cidade", "city", "estado", "uf"]
        ))
        localizacao = local_tag.get_text(strip=True) if local_tag else None

        return {
            "nome": nome,
            "site": site,
            "descricao_curta": descricao,
            "setor": setor,
            "estagio": estagio,
            "localizacao": localizacao,
            "ano_fundacao": None,
            "tamanho_time": None,
            "fontes_scraping": [self.key],
        }

    async def parse_list_page(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        startups: list[dict] = []

        for card in self._find_cards(soup):
            try:
                startup = self._parse_card(card, url)
                if startup and self.mark_seen(startup["site"]):
                    startups.append(startup)
                    self._stats["items_found"] += 1
            except Exception as e:
                logger.debug(f"[{self.key}] card parse: {e}")

        next_url = self._find_pagination(soup, url)
        if next_url and self.mark_seen(next_url):
            self._queued_pages.append(next_url)
            logger.info(f"[{self.key}] pagination: {next_url}")

        return startups

    async def parse_detail_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "lxml")
        title = extract_title(soup) or "Unknown"
        text = extract_main_text(html, url=url)

        setor_tag = soup.find(["meta", "span", "p"], attrs={"itemprop": "industry"}) or \
                    soup.find(class_=lambda c: c and "sector" in str(c).lower())
        setor = setor_tag.get("content") if hasattr(setor_tag, "get") else None
        if not setor:
            for tag in soup.find_all(["meta"], property="article:section"):
                setor = tag.get("content")
                break

        location_tag = soup.find(["meta", "span"], attrs={"itemprop": "address"}) or \
                      soup.find(class_=lambda c: c and "location" in str(c).lower())
        localizacao = location_tag.get("content") if hasattr(location_tag, "get") else None

        return {
            "nome": title.strip(),
            "site": url,
            "descricao_curta": text[:500] if text else None,
            "setor": setor,
            "estagio": EstagioEnum.DESCONHECIDO.value,
            "localizacao": localizacao,
            "ano_fundacao": None,
            "tamanho_time": None,
            "fontes_scraping": [self.key],
        }
