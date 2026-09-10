"""Seed the database with curated known AI startups + synthetic documents."""
from __future__ import annotations

import asyncio

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from scraper.config.settings import get_settings
from scraper.curated_seed import ALL_STARTUPS
from scraper.models import DocumentoCreate, EstagioEnum, StartupCreate
from scraper.pipelines.html_cleaner import extract_main_text, extract_title
from scraper.pipelines.loaders import DatabaseLoader


async def seed_startups() -> dict:
    settings = get_settings()
    stats = {"inserted": 0, "skipped": 0, "errors": 0}

    async with DatabaseLoader(settings) as loader:
        for s in ALL_STARTUPS:
            try:
                estagio = s.get("estagio", "desconhecido")
                if estagio not in [e.value for e in EstagioEnum]:
                    estagio = "desconhecido"

                startup = StartupCreate(
                    nome=s["nome"],
                    site=s.get("site"),
                    setor=s.get("setor"),
                    estagio=EstagioEnum(estagio),
                    localizacao=s.get("localizacao"),
                    descricao_curta=s.get("descricao_curta"),
                    ano_fundacao=s.get("ano_fundacao"),
                    tamanho_time=s.get("tamanho_time"),
                    fontes_scraping=["curated_seed"],
                )
                sid = await loader.upsert_startup(startup)
                if sid:
                    stats["inserted"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.error(f"Seed error for {s.get('nome')}: {e}")
                stats["errors"] += 1

    logger.info(f"Seed startups: {stats}")
    return stats


async def seed_documents_from_sites() -> dict:
    """Fetch the site of each startup and insert as document."""
    settings = get_settings()
    stats = {"docs": 0, "errors": 0, "skipped": 0}
    client = httpx.AsyncClient(timeout=30, follow_redirects=True)

    async with DatabaseLoader(settings) as loader:
        async with client:
            for s in ALL_STARTUPS:
                site = s.get("site")
                if not site or not site.startswith("http"):
                    stats["skipped"] += 1
                    continue

                try:
                    r = await client.get(site)
                    if r.status_code != 200:
                        stats["skipped"] += 1
                        continue

                    html = r.text
                    soup = BeautifulSoup(html, "lxml")
                    title = extract_title(soup) or s["nome"]
                    text = extract_main_text(html, url=site)

                    if not text or len(text) < 50:
                        stats["skipped"] += 1
                        continue

                    startup = StartupCreate(nome=s["nome"], site=site)
                    sid = await loader.upsert_startup(startup)
                    if not sid:
                        stats["skipped"] += 1
                        continue

                    doc = DocumentoCreate(
                        startup_nome=s["nome"],
                        tipo="site_institucional",
                        titulo=title,
                        conteudo_texto=text[:20_000],
                        url_fonte=site,
                        data_publicacao=None,
                        source_meta={"source": "curated_seed", "categoria": s.get("categoria", "unknown")},
                    )
                    result = await loader.insert_documento(doc, sid)
                    if result:
                        stats["docs"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.debug(f"Doc error for {s.get('nome')} @ {site}: {e}")
                    stats["errors"] += 1

    await client.aclose()
    logger.info(f"Seed docs: {stats}")
    return stats


async def main() -> None:
    print("Seeding startups...")
    s_stats = await seed_startups()
    print(f"  Startups: {s_stats}")

    print("Fetching startup sites for documents...")
    d_stats = await seed_documents_from_sites()
    print(f"  Documents: {d_stats}")

    async with DatabaseLoader(get_settings()) as loader:
        startups = await loader.get_startup_count()
        docs = await loader.get_documento_count()
        print(f"\nTotal: {startups} startups, {docs} documentos")


if __name__ == "__main__":
    asyncio.run(main())
