"""Enrichment spider — fetches details from startup websites.

For each startup in the database with < 3 documents, scrape its website
to extract description, sector, founding year, and text content.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.settings import Settings, get_settings
from scraper.models import DocumentoCreate
from scraper.pipelines.html_cleaner import (
    clean_text,
    extract_main_text,
    extract_meta_description,
    extract_title,
)
from scraper.pipelines.http_client import HttpClient
from scraper.pipelines.loaders import DatabaseLoader


class EnrichmentSpider:
    """Scrape startup websites and insert structured documents."""

    AI_KEYWORDS = {
        "ai", "inteligência artificial", "machine learning", "deep learning",
        "neural", "gpt", "llm", "langchain", "nlp", "nlu", "computer vision",
        "ocr", "chatbot", "generative", "generativa", "ia generativa",
        "artificial intelligence", "mlops", "rag", "embedding", "vector db",
        "transformer", "llama", "claude", "gemini", "openai",
        "natural language", "speech", "voice", "cv",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.http: HttpClient | None = None
        self.stats = {"startups_visited": 0, "docs_inserted": 0, "errors": 0}

    def _is_ai_related(self, text: str) -> bool:
        if not text:
            return False
        lower = text.lower()
        return any(kw in lower for kw in self.AI_KEYWORDS)

    async def scrape_startup(self, row: dict, http: HttpClient) -> dict | None:
        """Fetch startup site, extract structured data."""
        site = row.get("site") or ""
        if not site or not site.startswith("http"):
            return None

        try:
            html = await http.get_text(site)
            if not html:
                return None
        except Exception as e:
            logger.debug(f"Failed to fetch {site}: {e}")
            return None

        soup = BeautifulSoup(html, "lxml")
        title = extract_title(soup) or row.get("nome", "")
        description = extract_meta_description(soup)
        text = extract_main_text(html, url=site)

        # Try to extract sector from page text
        sector = None
        sector_patterns = [
            r"(?i)(?:sector|setor|vertical|industry)[\s:]+([A-Za-zÀ-ÿ\s]+?)(?:\n|,|\.|;)",
        ]
        for pat in sector_patterns:
            try:
                m = re.search(pat, text or "")
            except re.error:
                continue
            if m:
                sector = m.group(1).strip()[:50] or m.group(0).strip()[:50]
                break

        # Try to extract year from text
        year = None
        year_match = re.search(r"\b(20[12][0-9])\b", (text or "")[:500])
        if year_match:
            year = int(year_match.group(1))

        # Check if AI-related
        is_ai = self._is_ai_related(text or "") or self._is_ai_related(description or "")
        ai_signals = []
        for kw in self.AI_KEYWORDS:
            if kw in (text or "").lower():
                ai_signals.append(kw)

        return {
            "title": clean_text(title),
            "description": clean_text(description)[:300],
            "text": clean_text(text or "")[:20_000],
            "sector": sector,
            "year": year,
            "is_ai": is_ai,
            "ai_signals": ai_signals[:5],
            "site": site,
        }

    async def run(self, min_docs: int = 3, max_startups: int = 50) -> dict:
        """Enrich startups with < min_docs documents.

        For each startup, fetches multiple pages (homepage, about, blog) to
        accumulate documents.
        """
        self.stats = {
            "startups_visited": 0,
            "docs_inserted": 0,
            "errors": 0,
            "startups_at_target": 0,
        }
        async with HttpClient(self.settings) as http:
            self.http = http
            async with DatabaseLoader(self.settings) as loader:
                underdocs = await loader.get_startups_without_min_docs(min_docs)
                if not underdocs:
                    logger.info("No startups needing enrichment")
                    return self.stats

                to_process = underdocs[:max_startups]
                logger.info(f"Enriching {len(to_process)} startups")

                for row in to_process:
                    try:
                        count = await self._enrich_one(row, loader)
                        if count > 0:
                            self.stats["docs_inserted"] += count
                        self.stats["startups_visited"] += 1
                    except Exception as e:
                        logger.error(f"Enrichment error for {row.get('nome')}: {e}")
                        self.stats["errors"] += 1

        logger.info(f"Enrichment done: {self.stats}")
        return self.stats

    async def _enrich_one(self, row: dict, loader: DatabaseLoader) -> int:
        """Enrich a single startup by fetching multiple pages."""
        site = row.get("site") or ""
        if not site or not site.startswith("http"):
            return 0
        sid = row["id"]

        from urllib.parse import urljoin, urlparse
        parsed = urlparse(site)
        base = f"{parsed.scheme}://{parsed.netloc}"
        candidate_paths = [
            "",  # homepage
            "/about", "/sobre", "/empresa", "/company", "/quem-somos",
            "/products", "/produtos", "/plataforma", "/platform",
            "/blog", "/noticias", "/news", "/cases", "/clientes",
            "/careers", "/carreiras", "/jobs", "/vagas",
            "/team", "/equipe", "/founders", "/fundadores",
            "/contact", "/contato", "/manifesto", "/mission",
        ]

        seen_urls: set[str] = set()
        inserted = 0
        max_docs_per_startup = 5

        for path in candidate_paths:
            if inserted >= max_docs_per_startup:
                break
            target_url = urljoin(base, path) if path else site
            if target_url in seen_urls:
                continue
            seen_urls.add(target_url)

            try:
                html = await self.http.get_text(target_url)
            except Exception:
                continue
            if not html or len(html) < 200:
                continue
            soup = BeautifulSoup(html, "lxml")
            text = extract_main_text(html, url=target_url)
            if not text or len(text) < 100:
                continue
            title = extract_title(soup) or f"{row['nome']} - {path or 'home'}"

            doc = DocumentoCreate(
                startup_nome=row["nome"],
                tipo="site_institucional",
                titulo=title[:200],
                conteudo_texto=clean_text(text)[:15_000],
                url_fonte=target_url,
                data_publicacao=None,
                source_meta={
                    "source": "enrichment_spider",
                    "path": path or "/",
                },
            )
            try:
                result = await loader.insert_documento(doc, sid)
                if result:
                    inserted += 1
                    logger.debug(f"[{row['nome']}] +1 doc from {target_url}")
            except Exception:
                continue

            # Find more internal links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("/") and not href.startswith(base):
                    continue
                full = urljoin(base, href)
                path_only = full.replace(base, "")
                if not path_only.startswith("/"):
                    continue
                if path_only in ["/", ""]:
                    continue
                if any(skip in path_only.lower() for skip in [
                    "login", "signup", "signin", "register",
                    "twitter.com", "facebook.com", "instagram.com", "linkedin.com",
                    "youtube.com", "wa.me", "whatsapp", "mailto:",
                ]):
                    continue
                if any(path_only.startswith(p) for p in candidate_paths):
                    continue
                if any(path_only.endswith(ext) for ext in [
                    ".pdf", ".jpg", ".png", ".svg", ".zip", ".xml", ".json", ".css", ".js"
                ]):
                    continue
                if full not in seen_urls and inserted < max_docs_per_startup:
                    seen_urls.add(full)

        return inserted
