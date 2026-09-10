"""Post-process articles.jsonl into documentos table.

Reads articles collected from news sources, fetches their full text, and
inserts them as documentos linked to mentioned startups.
"""
from __future__ import annotations

import asyncio
import json
import re

from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.settings import get_settings
from scraper.models import DocumentoCreate, StartupCreate
from scraper.pipelines.html_cleaner import extract_main_text, extract_title, parse_date
from scraper.pipelines.http_client import HttpClient
from scraper.pipelines.loaders import DatabaseLoader

SKIP_BRANDS = {
    "OpenAI", "Google", "Meta", "Amazon", "Microsoft", "Apple", "NVIDIA",
    "Anthropic", "DeepMind", "Salesforce", "Oracle", "IBM", "Intel", "AMD",
    "Brasil", "Brazil", "São Paulo", "Rio", "Latam", "LatAm", "Silicon Valley",
    "Bay Area", "Estados Unidos", "EUA", "Reino Unido", "UE", "Europa",
    "StartSe", "Distrito", "Latitud", "100 Open Startups", "Cubo",
    "Endeavor", "BNDES", "Sebrae", "FGV", "USP", "MIT", "Stanford",
    "Mercado Livre", "Stone", "Nubank", "PicPay", "iFood", "XP",
}


def extract_startup_candidates(text: str, min_len: int = 4, max_len: int = 50) -> list[str]:
    """Heuristic extraction of company-name-like tokens from text."""
    candidates: set[str] = set()
    # Pattern 1: Capitalized words (company names)
    pattern = r"\b([A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý0-9&\-\.]+(?:\s+[A-ZÀ-Ы][a-zà-ÿA-ZÀ-Ý0-9&\-\.]+){0,3})\b"
    for match in re.finditer(pattern, text):
        name = match.group(1).strip()
        if min_len <= len(name) <= max_len:
            words = name.split()
            if any(w in SKIP_BRANDS for w in words):
                continue
            # Filter out common non-startup words
            if any(name.endswith(s) for s in [" Brasil", " Global", " Tech", " AI", " SaaS"]):
                continue
            if name.lower() in {"a", "e", "ou", "the", "of", "de", "para", "com", "em"}:
                continue
            if re.match(r"^[A-Z]{2,}$", name):
                continue
            candidates.add(name)
    return sorted(candidates)[:10]


async def process_article(
    article: dict,
    http: HttpClient,
    loader: DatabaseLoader,
) -> int:
    """Fetch article body, find mentioned startups, insert documents."""
    url = article.get("url")
    if not url:
        return 0
    titulo = article.get("titulo", "Untitled")
    data_str = article.get("data_publicacao") or article.get("data")

    html = await http.get_text(url)
    if not html:
        return 0
    soup = BeautifulSoup(html, "lxml")
    text = extract_main_text(html, url=url)
    if not text or len(text) < 100:
        return 0
    final_title = extract_title(soup) or titulo
    data = parse_date(data_str) if isinstance(data_str, str) else data_str

    mentioned = extract_startup_candidates(text)
    if not mentioned:
        return 0

    inserted = 0
    for startup_name in mentioned[:3]:
        try:
            startup = StartupCreate(nome=startup_name)
            sid = await loader.upsert_startup(startup)
            if sid:
                doc = DocumentoCreate(
                    startup_nome=startup_name,
                    tipo="noticia",
                    titulo=final_title,
                    conteudo_texto=text[:15_000],
                    url_fonte=url,
                    data_publicacao=data,
                    source_meta={
                        "source": article.get("fontes_scraping", ["unknown"])[0] if article.get("fontes_scraping") else "unknown",
                        "mentioned_in_news": True,
                    },
                )
                result = await loader.insert_documento(doc, sid)
                if result:
                    inserted += 1
        except Exception as e:
            logger.debug(f"Failed to process mention '{startup_name}': {e}")
    return inserted


async def main() -> None:
    settings = get_settings()
    articles_path = settings.exports_dir / "articles.jsonl"
    if not articles_path.exists():
        print(f"No articles file at {articles_path}")
        return

    with articles_path.open() as f:
        articles = [json.loads(line) for line in f if line.strip()]

    print(f"Processing {len(articles)} articles...")

    total_inserted = 0
    async with HttpClient(settings) as http:
        async with DatabaseLoader(settings) as loader:
            for i, article in enumerate(articles):
                try:
                    n = await process_article(article, http, loader)
                    total_inserted += n
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i+1}/{len(articles)} articles, {total_inserted} docs inserted")
                except Exception as e:
                    logger.error(f"Article {article.get('url')}: {e}")

    print(f"\nDone: {total_inserted} documents inserted from {len(articles)} articles")


if __name__ == "__main__":
    asyncio.run(main())
