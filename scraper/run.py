"""Scraper CLI entrypoint.

Usage:
    python -m scraper.run [--source <key>] [--enrich] [--stats]

Examples:
    python -m scraper.run --source distrito --limit 5
    python -m scraper.run --enrich
    python -m scraper.run --stats
    python -m scraper.run --all
    python -m scraper.run --source wow --output jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from scraper.config.settings import Settings, get_settings
from scraper.config.sources import SOURCES_BY_KEY, get_enabled_sources
from scraper.pipelines.http_client import HttpClient
from scraper.pipelines.jsonl_exporter import JSONLExporter
from scraper.pipelines.loaders import DatabaseLoader

AVAILABLE_SPIDERS = {
    "distrito": "scraper.spiders.distrito",
    "open100": "scraper.spiders.open100",
    "startse": "scraper.spiders.startse",
    "latitud": "scraper.spiders.latitud",
    "cubo": "scraper.spiders.cubo",
    "ace": "scraper.spiders.ace",
    "endeavor": "scraper.spiders.endeavor",
    "abstartups": "scraper.spiders.abstartups",
    "bossa": "scraper.spiders.bossa",
    "anjos": "scraper.spiders.anjos",
    "darwin": "scraper.spiders.darwin",
    "liga": "scraper.spiders.liga",
    "wow": "scraper.spiders.wow",
    "inovativa": "scraper.spiders.inovativa",
    "brazil_journal": "scraper.spiders.brazil_journal",
    "neofeed": "scraper.spiders.neofeed",
    "exame": "scraper.spiders.exame",
    "startups_com_br": "scraper.spiders.startups_com_br",
    "pegn": "scraper.spiders.pegn",
    "valor": "scraper.spiders.valor",
    "meio_mensagem": "scraper.spiders.meio_mensagem",
    "mobile_time": "scraper.spiders.mobile_time",
}


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
        level=level,
    )
    logger.add(
        "scraper_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function} — {message}",
    )


def load_spider(key: str):
    if key not in AVAILABLE_SPIDERS:
        logger.error(f"Unknown spider: {key}. Available: {list(AVAILABLE_SPIDERS.keys())}")
        sys.exit(1)
    import importlib
    module = importlib.import_module(AVAILABLE_SPIDERS[key])
    return module.build()


async def run_spider(
    key: str,
    *,
    settings: Settings | None = None,
    limit: int | None = None,
    enrich: bool = False,
    dry_run: bool = False,
    output: str = "jsonl",
) -> list[dict]:
    settings = settings or get_settings()
    spider = load_spider(key)
    is_news = SOURCES_BY_KEY.get(key) and SOURCES_BY_KEY[key].category.value == "news"

    async with HttpClient(settings) as http:
        items = await spider.run(http)

    if limit:
        items = items[:limit]

    logger.info(f"[{key}] Collected {len(items)} items")

    if dry_run:
        logger.info(f"[{key}] Dry run — skipping write")
        return items

    if output == "jsonl":
        exporter = JSONLExporter(settings)
        if is_news:
            exporter.write_articles(items, append=True)
        else:
            exporter.write_startups(items, append=True)
        return items

    if output == "postgres":
        from scraper.models import DocumentoCreate, StartupCreate
        if is_news:
            logger.info(f"[{key}] News spider — fetching detail pages before persisting")
            docs = []
            async with HttpClient(settings) as http2:
                async with DatabaseLoader(settings) as loader:
                    for art in items:
                        try:
                            url = art.get("url")
                            if not url:
                                continue
                            resp = await http2.get_text(url)
                            if resp:
                                from bs4 import BeautifulSoup

                                from scraper.pipelines.html_cleaner import extract_main_text
                                soup = BeautifulSoup(resp, "lxml")
                                text = extract_main_text(resp, url=url)
                                from scraper.pipelines.html_cleaner import extract_title, parse_date
                                titulo = extract_title(soup) or art.get("titulo", "Untitled")
                                date_tag = soup.find("time") or soup.find("meta", attrs={"property": "article:published_time"})
                                data = parse_date(date_tag.get("datetime") if date_tag and date_tag.get("datetime") else (date_tag.get("content") if date_tag else None))
                                for mentioned in art.get("startups_mentioned", [])[:3]:
                                    doc = {
                                        "startup_nome": mentioned,
                                        "tipo": "noticia",
                                        "titulo": titulo,
                                        "conteudo_texto": text[:20_000] if text else "",
                                        "url_fonte": url,
                                        "data_publicacao": data,
                                        "source_meta": {"source": key, "extracted_from_news": True},
                                    }
                                    docs.append(doc)
                        except Exception as e:
                            logger.error(f"[{key}] Failed to process article: {e}")
                    if docs:
                        for doc in docs:
                            try:
                                startup = StartupCreate(nome=doc["startup_nome"])
                                sid = await loader.upsert_startup(startup)
                                if sid:
                                    await loader.insert_documento(DocumentoCreate(**doc), sid)
                            except Exception as e:
                                logger.error(f"[{key}] DB write: {e}")
        else:
            async with DatabaseLoader(settings) as loader:
                loaded = 0
                for item in items:
                    try:
                        startup = StartupCreate(**item)
                        startup_id = await loader.upsert_startup(startup)
                        if startup_id:
                            loaded += 1
                    except Exception as e:
                        logger.error(f"[{key}] Failed to upsert startup: {e}")
                logger.info(f"[{key}] Loaded {loaded} startups to DB")
        return items

    logger.warning(f"Unknown output: {output}")
    return items


async def run_all_sources(*, settings: Settings | None = None, max_concurrent: int = 3, output: str = "jsonl") -> dict:
    settings = settings or get_settings()
    sem = asyncio.Semaphore(max_concurrent)
    total_stats = {"sources": 0, "startups": 0, "errors": 0}

    async def run_one(key: str) -> dict:
        async with sem:
            try:
                items = await run_spider(key, settings=settings, output=output, dry_run=False)
                return {"key": key, "items": len(items), "error": None}
            except Exception as e:
                logger.error(f"[{key}] Fatal: {e}")
                return {"key": key, "items": 0, "error": str(e)}

    tasks = [run_one(s.key) for s in get_enabled_sources()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            total_stats["errors"] += 1
            continue
        total_stats["sources"] += 1
        total_stats["startups"] += r["items"]
        if r["error"]:
            total_stats["errors"] += 1

    return total_stats


async def show_stats(settings: Settings | None = None) -> None:
    settings = settings or get_settings()

    print(f"\n{'='*50}")
    print("  NVIDIA Radar — Database & Files Stats")
    print(f"{'='*50}")

    exporter = JSONLExporter(settings)
    jsonl_stats = exporter.stats()
    print(f"  JSONL startups: {jsonl_stats['startups_count']}")
    print(f"  JSONL docs:     {jsonl_stats['docs_count']}")
    print(f"  Startups file:  {jsonl_stats['startups_file']}")

    try:
        async with DatabaseLoader(settings) as loader:
            startups = await loader.get_startup_count()
            docs = await loader.get_documento_count()
            underdocs = await loader.get_startups_without_min_docs(3)
            print(f"  Postgres startups:    {startups}")
            print(f"  Postgres documentos: {docs}")
            print(f"  Startups < 3 docs:   {len(underdocs)}")
    except Exception as e:
        print(f"  Postgres: not available ({type(e).__name__})")
    print(f"{'='*50}\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="NVIDIA Radar Scraper")
    parser.add_argument("--source", type=str, help="Run only this spider")
    parser.add_argument("--all", action="store_true", help="Run all enabled spiders")
    parser.add_argument("--enrich", action="store_true", help="Enrich startups with <3 docs")
    parser.add_argument("--enrich-limit", type=int, default=50, help="Max startups to enrich")
    parser.add_argument("--stats", action="store_true", help="Show DB stats and exit")
    parser.add_argument("--dry-run", action="store_true", help="Scrape without writing")
    parser.add_argument("--limit", type=int, default=None, help="Max items per spider")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    parser.add_argument("--output", type=str, default="jsonl", choices=["jsonl", "postgres"], help="Output mode")
    args = parser.parse_args()

    setup_logging(args.log_level)
    settings = get_settings()

    if args.stats:
        await show_stats(settings)
        return

    if args.enrich:
        from scraper.spiders.enrichment import EnrichmentSpider
        spider = EnrichmentSpider(settings)
        result = await spider.run(min_docs=3, max_startups=args.enrich_limit)
        print(f"\nEnrichment result: {result}")
        return

    if args.all:
        result = await run_all_sources(settings=settings, output=args.output)
        logger.info(f"Total: {result}")
        return

    if args.enrich:
        logger.info("Enrichment done")
        return

    if args.source:
        await run_spider(
            args.source,
            settings=settings,
            dry_run=args.dry_run,
            limit=args.limit,
            output=args.output,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
