"""Curadoria — limpa startups e documentos baseado em regras de qualidade."""
from __future__ import annotations

import asyncio
import re

from loguru import logger

from scraper.config.settings import Settings, get_settings
from scraper.pipelines.loaders import DatabaseLoader

JUNK_WORDS = {
    "como", "copel", "apesar", "agora", "ainda", "achavam", "além", "américa latina",
    "banco central", "brasil", "todos", "após", "assim", "através", "outros",
    "antes", "depois", "porque", "embora", "enquanto", "sempre", "nunca",
    "talvez", "apenas", "também", "contudo", "entretanto", "porém", "portanto",
    "the", "a", "o", "and", "or", "in", "on", "at", "to", "for", "of",
    "we", "you", "i", "it", "this", "that", "with", "by", "from",
    "via", "mas", "para", "com", "sem", "por", "ser", "ter", "estar",
    "foi", "vai", "aqui", "ali", "lá", "sim", "não", "só",
    "they", "their", "be", "is", "are", "was", "were", "have", "has",
    "tencent", "google", "openai", "anthropic", "meta", "microsoft", "amazon",
    "intel", "amd", "nvidia", "apple", "ibm", "oracle", "salesforce",
}

JUNK_PATTERNS = [
    r"^[\d\W]+$",  # only digits/symbols
    r"^[A-Z]{1,2}$",  # 1-2 letter abbreviations
    r"^\W+",
    r"\W$",
    r"^(são|rio|brasil|brazil|sp|rj|mg|us|eua)$",  # places only
]


def is_valid_startup_name(nome: str) -> bool:
    if not nome or len(nome) < 3 or len(nome) > 80:
        return False
    nome_clean = nome.strip()
    if nome_clean.lower() in JUNK_WORDS:
        return False
    for pat in JUNK_PATTERNS:
        if re.search(pat, nome_clean, re.IGNORECASE):
            return False
    # Must have at least 2 letters
    if sum(c.isalpha() for c in nome_clean) < 3:
        return False
    return True


async def curate(settings: Settings | None = None) -> dict:
    """Delete junk startups and consolidate documents."""
    settings = settings or get_settings()
    stats = {"deleted_startups": 0, "deleted_docs": 0, "kept_startups": 0}

    async with DatabaseLoader(settings) as loader:
        async with loader.pool.acquire() as conn:
            # Find startups with junk names
            junk = await conn.fetch(
                "SELECT id, nome FROM startups WHERE site IS NULL OR site = ''"
            )
            for row in junk:
                if not is_valid_startup_name(row["nome"]):
                    await conn.execute("DELETE FROM documentos WHERE startup_id = $1", row["id"])
                    await conn.execute("DELETE FROM startups WHERE id = $1", row["id"])
                    stats["deleted_startups"] += 1

            # Delete duplicated startups (keep first occurrence)
            dups = await conn.fetch(
                """
                SELECT LOWER(nome) as n, array_agg(id ORDER BY id) as ids
                FROM startups
                WHERE site IS NOT NULL AND site <> ''
                GROUP BY LOWER(nome)
                HAVING COUNT(*) > 1
                """
            )
            for row in dups:
                ids = row["ids"]
                keep_id = ids[0]
                delete_ids = ids[1:]
                # Move documents to keep_id
                await conn.execute(
                    "UPDATE documentos SET startup_id = $1 WHERE startup_id = ANY($2)",
                    keep_id,
                    delete_ids,
                )
                await conn.execute(
                    "DELETE FROM startups WHERE id = ANY($1)", delete_ids
                )
                stats["deleted_startups"] += len(delete_ids)

            total_startups = await conn.fetchval("SELECT COUNT(*) FROM startups")
            stats["kept_startups"] = total_startups

    logger.info(f"Curate: {stats}")
    return stats


if __name__ == "__main__":
    asyncio.run(curate())
