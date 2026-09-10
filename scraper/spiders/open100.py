"""100 Open Startups spider — startup ranking platform (ranking por corporação)."""
from __future__ import annotations

from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.sources import SOURCES_BY_KEY
from scraper.models import EstagioEnum
from scraper.spiders._base_aggregator import AggregatorSpider


class Open100Spider(AggregatorSpider):
    """100 Open Startups ranking.

    O ranking é uma tabela de soluções por corporação — cada linha referencia a
    startup (coluna "Startup") com link para o perfil. `_find_cards` genérico não
    pega `<tr>`, então `parse_list_page` é sobrescrito para lidar com linhas da
    tabela além dos cards padrão.
    """

    CARD_SELECTORS = [
        "a[href*='/companies/']",
        "a[href*='/company/']",
        "a[href*='/solutions/']",
        ".ranking-item",
        ".company-card",
        ".table-row",
        "a[href*='/startup/']",
        ".startup-card",
        ".portfolio-item",
    ]

    def _parse_table_row(self, row, base_url: str):
        link_tag = row.find("a", href=True)
        if not link_tag:
            return None
        site = link_tag.get("href", "")
        if not site.startswith(("http", "/")):
            return None
        for skip in ["/tag/", "/category/", "/author/", "/page/", "#"]:
            if skip in site:
                return None

        nome = link_tag.get_text(strip=True) or row.get_text(strip=True)[:80]
        if not nome:
            return None

        cells = row.find_all("td")
        setor = cells[1].get_text(strip=True) if len(cells) > 1 else None
        desc_tag = row.find(["p", ".description", ".desc"])
        descricao = desc_tag.get_text(strip=True)[:500] if desc_tag else None

        return {
            "nome": nome,
            "site": site,
            "descricao_curta": descricao,
            "setor": setor,
            "estagio": EstagioEnum.DESCONHECIDO.value,
            "localizacao": None,
            "ano_fundacao": None,
            "tamanho_time": None,
            "fontes_scraping": [self.key],
        }

    async def parse_list_page(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        startups: list[dict] = []
        for row in soup.select("table tbody tr, table tr"):
            try:
                startup = self._parse_table_row(row, url)
                if startup and self.mark_seen(startup["site"]):
                    startups.append(startup)
                    self._stats["items_found"] += 1
            except Exception as e:
                logger.debug(f"[{self.key}] table row parse: {e}")

        next_url = self._find_pagination(soup, url)
        if next_url and self.mark_seen(next_url):
            self._queued_pages.append(next_url)
            logger.info(f"[{self.key}] pagination: {next_url}")

        return startups + await super().parse_list_page(html, url)


def build() -> Open100Spider:
    return Open100Spider(SOURCES_BY_KEY["open100"])
