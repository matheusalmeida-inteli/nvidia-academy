"""PostgreSQL async loader for scraped data."""
from __future__ import annotations

import asyncpg
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from loguru import logger

from scraper.config.settings import Settings, get_settings
from scraper.models import DocumentoCreate, StartupCreate


class DatabaseLoader:
    """Async PostgreSQL loader with upsert semantics."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pool: asyncpg.Pool | None = None

    async def __aenter__(self) -> DatabaseLoader:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            database=self.settings.postgres_db,
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
            min_size=1,
            max_size=self.settings.scraper_max_concurrency * 2,
        )
        logger.info("Postgres pool initialized")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DatabaseLoader not connected")
        return self._pool

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def upsert_startup(self, startup: StartupCreate) -> int | None:
        """Insert or update a startup by nome (case-insensitive). Return its id."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO startups (
                    nome, site, setor, estagio, localizacao,
                    descricao_curta, ano_fundacao, tamanho_time, fontes_scraping
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (LOWER(nome)) DO UPDATE
                    SET site = EXCLUDED.site,
                        setor = EXCLUDED.setor,
                        estagio = EXCLUDED.estagio,
                        localizacao = EXCLUDED.localizacao,
                        descricao_curta = EXCLUDED.descricao_curta,
                        ano_fundacao = EXCLUDED.ano_fundacao,
                        tamanho_time = EXCLUDED.tamanho_time,
                        updated_at = NOW()
                RETURNING id
                """,
                startup.nome,
                startup.site,
                startup.setor,
                startup.estagio.value,
                startup.localizacao,
                startup.descricao_curta,
                startup.ano_fundacao,
                startup.tamanho_time,
                startup.fontes_scraping,
            )
            if row:
                logger.debug(f"Upserted startup id={row['id']} name={startup.nome!r}")
                return row["id"]
            return None

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def insert_documento(
        self,
        doc: DocumentoCreate,
        startup_id: int,
    ) -> int | None:
        """Insert a document linked to a startup."""
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO documentos (
                        startup_id, tipo, titulo, conteudo_texto,
                        url_fonte, data_publicacao, source_meta
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (startup_id, url_fonte) DO UPDATE
                        SET conteudo_texto = EXCLUDED.conteudo_texto,
                            titulo = EXCLUDED.titulo,
                            data_publicacao = EXCLUDED.data_publicacao,
                            source_meta = documentos.source_meta || EXCLUDED.source_meta
                    RETURNING id
                    """,
                    startup_id,
                    doc.tipo.value,
                    doc.titulo,
                    doc.conteudo_texto,
                    doc.url_fonte,
                    doc.data_publicacao,
                    json.dumps(doc.source_meta),
                )
                if row:
                    logger.debug(f"Inserted doc id={row['id']} for startup_id={startup_id}")
                    return row["id"]
                return None
            except Exception as e:
                logger.error(f"Failed to insert doc for startup_id={startup_id}: {e}")
                return None

    async def get_startup_count(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM startups") or 0

    async def get_documento_count(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM documentos") or 0

    async def get_startups_without_min_docs(self, min_docs: int = 3) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.nome, s.site, COUNT(d.id) AS doc_count
                FROM startups s
                LEFT JOIN documentos d ON d.startup_id = s.id
                GROUP BY s.id
                HAVING COUNT(d.id) < $1
                ORDER BY doc_count ASC
                """,
                min_docs,
            )
            return [dict(r) for r in rows]