"""FastAPI bridge — multi-agent pipeline + candidates + nurture."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "nvidia_radar")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "nvidia_radar_pass")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "nvidia_radar")


# ---- Request/Response models ----

class RecommendationItem(BaseModel):
    """Uma recomendação tecnológica individual gerada pelo agente."""
    tecnologia: str
    justificativa_tecnica: str
    justificativa_negocio: str
    prioridade: str
    complexidade: str
    proxima_acao: str
    fontes_rag: list[dict] = Field(default_factory=list)
    evidencias: list[str] = Field(default_factory=list)
    origem_recomendacao: str = ""
    score_final: float = 0.0
    score_breakdown: dict = Field(default_factory=dict)
    regra_ids: list[str] = Field(default_factory=list)


class BriefingResponse(BaseModel):
    """Briefing executivo completo de uma startup (fit, nurture e recomendações)."""
    empresa: str
    setor: str
    maturidade_ai: str
    score_maturidade: float
    inception_fit_score: float = 0.0
    wrapper_warning: bool = False
    fit_breakdown: dict = Field(default_factory=dict)
    criterio_selecao: str = ""
    nurture_suggestion: str = ""
    recomendacoes: list[RecommendationItem] = Field(default_factory=list)
    proximos_comerciais: list[str] = Field(default_factory=list)
    proximos_tecnicos: list[str] = Field(default_factory=list)
    proximos_comunitarios: list[str] = Field(default_factory=list)
    fontes_consultadas: list[str] = Field(default_factory=list)
    fontes_rag: list[dict] = Field(default_factory=list)
    generated_at: str = ""
    evidencia_insuficiente: bool = False


class StartupResult(BaseModel):
    """Resultado de uma startup enriquecido pelo pipeline (classificação + evidências)."""
    nome: str
    site: str | None = None
    setor: str | None = None
    estagio: str = "N/A"
    localizacao: str | None = None
    descricao_curta: str | None = None
    categoria: str = "N/A"
    confianca: float = 0.0
    inception_fit_score: float = 0.0
    wrapper_warning: bool = False
    moat_score: float = 0.0
    evidencias_count: int = 0
    recomendacoes: list[RecommendationItem] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Resposta consolidada de uma consulta de pipeline multi-agente."""
    startups: list[StartupResult]
    briefing: BriefingResponse | None = None
    query_keywords: list[str] = Field(default_factory=list)
    total_found: int = 0


class QueryRequest(BaseModel):
    """Corpo da consulta de pipeline (query textual + limite de startups)."""
    query: str = Field(..., min_length=1, max_length=500)
    max_startups: int = Field(default=10, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Rejeita query em branco (só espaços) antes de chegar ao pipeline.

        O pipeline tem fallback `["startup", "ai", "brasil"]` que mascara
        entradas ruins — preferimos 422 explícito a briefing enganoso.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("query não pode ser apenas espaços em branco")
        return stripped


# ---- Candidate models ----

class CandidateCreate(BaseModel):
    """Dados para inserir um novo candidato (vínculo com startup)."""
    startup_id: int
    notes: str | None = None
    assigned_to: str | None = None
    inception_fit_score: float | None = None
    categoria_ai: str | None = None
    wrapper_warning: bool | None = None
    moat_score: float | None = None
    tech_score: float | None = None
    sector_score: float | None = None
    traction_score: float | None = None
    nurture_cadence: str | None = None
    next_action_date: str | None = None
    next_action_type: str | None = None
    next_action_desc: str | None = None


class CandidateUpdate(BaseModel):
    """Campos atualizáveis de um candidato (status, notas, nurture, próximas ações)."""
    status: str | None = None
    notes: str | None = None
    assigned_to: str | None = None
    next_action_date: str | None = None
    next_action_type: str | None = None
    next_action_desc: str | None = None
    nurture_cadence: str | None = None


class CandidateResponse(BaseModel):
    """Visão completa de um candidato com scores do funil (Inception fit, moat, nurture)."""
    id: int
    startup_id: int
    startup_nome: str | None = None
    inception_fit_score: float = 0.0
    status: str = "identificado"
    categoria_ai: str = "desconhecido"
    wrapper_warning: bool = False
    fit_justification: str | None = None
    moat_score: float = 0.0
    tech_score: float = 0.0
    sector_score: float = 0.0
    traction_score: float = 0.0
    nurture_cadence: str = "mensal"
    next_action_date: str | None = None
    next_action_type: str | None = None
    next_action_desc: str | None = None
    notes: str | None = None
    assigned_to: str | None = None
    last_contacted_at: str | None = None
    last_contacted_type: str | None = None
    created_at: str | None = None


class NurtureLogEntry(BaseModel):
    """Registro de uma ação de nurture (canal, desfecho e notas)."""
    action_type: str
    channel: str | None = None
    outcome: str | None = None
    notes: str | None = None


class NurtureLogResponse(BaseModel):
    """Resposta persistida de um log de nurture."""
    id: int
    candidate_id: int
    action_type: str
    channel: str | None = None
    outcome: str | None = None
    notes: str | None = None
    created_at: str | None = None


_app: FastAPI | None = None


def _pool():
    """Cria um pool asyncpg para o PostgreSQL (config via variáveis de ambiente)."""
    import asyncpg
    return asyncpg.create_pool(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
        database=POSTGRES_DB, min_size=1, max_size=5,
    )


def get_app() -> FastAPI:
    """Constrói a aplicação FastAPI com todos os endpoints (singleton em _app)."""
    global _app
    if _app is not None:
        return _app

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    _app = FastAPI(
        title="NVIDIA Radar API",
        description="Intelligence platform for NVIDIA Inception Manager — Atrair / Qualificar / Nutrir",
        version="2.1.0",
        lifespan=lifespan,
    )
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @_app.get("/health")
    async def health():
        """Healthcheck simples para orquestração/supervisão."""
        return {"status": "ok", "service": "nvidia-radar-api", "version": "2.1.0"}

    # ---- Startups ----

    @_app.get("/startups")
    async def list_startups(
        setor: str | None = None,
        estagio: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        """Lista startups com filtros (setor, estágio, busca) e contagem de documentos."""
        pool = await _pool()
        async with pool.acquire() as conn:
            where, params, p = ["1=1"], [], 1
            if setor:
                where.append(f"LOWER(setor) LIKE ${p}")
                params.append(f"%{setor.lower()}%")
                p += 1
            if estagio:
                where.append(f"estagio = ${p}")
                params.append(estagio)
                p += 1
            if search:
                where.append(f"LOWER(nome) LIKE ${p}")
                params.append(f"%{search.lower()}%")
                p += 1
            where_sql = " AND ".join(where)
            rows = await conn.fetch(
                f"""SELECT s.id, s.nome, s.site, s.setor, s.estagio, s.localizacao,
                          s.descricao_curta,
                          (SELECT COUNT(*) FROM documentos d WHERE d.startup_id = s.id) AS doc_count
                   FROM startups s WHERE {where_sql}
                   ORDER BY s.id DESC LIMIT ${p} OFFSET ${p+1}""",
                *params, limit, offset,
            )
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM startups s WHERE {where_sql}", *params
            )
        await pool.close()
        return {
            "startups": [
                {**dict(r), "documentos": r["doc_count"]} for r in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ---- Multi-agent query ----

    async def _build_query_payload(req: QueryRequest) -> dict:
        """Roda o pipeline multi-agente e monta o payload estruturado da resposta."""
        from agents.graph import run_pipeline
        result = await run_pipeline(req.query)

        if hasattr(result, "__dict__"):
            result = result.__dict__

        recommendations = result.get("recommendations", []) or []
        classifications = result.get("classifications", []) or []
        evidence_results = result.get("evidence_results", []) or []
        retrieved_startups = result.get("retrieved_startups", []) or []
        query_result = result.get("query_result", {}) or {}
        briefing_data = result.get("briefing", None)

        startups_out = []
        for rec in recommendations[: req.max_startups]:
            rec = _dict(rec)
            nome = rec.get("nome", "")
            classif = _dict(next(
                (c for c in classifications if c.get("nome") == nome), {}
            ))
            evidence = _dict(next(
                (e for e in evidence_results if e.get("nome") == nome), {}
            ))
            startup = next(
                (s for s in retrieved_startups if s.get("nome") == nome), {}
            )
            startup = _dict(startup)

            recs_out = []
            for r in rec.get("recomendacoes", []) or []:
                r = _dict(r)
                try:
                    recs_out.append(RecommendationItem(**r))
                except Exception:
                    pass

            startups_out.append(StartupResult(
                nome=nome,
                site=startup.get("site"),
                setor=startup.get("setor"),
                estagio=startup.get("estagio", "N/A"),
                localizacao=startup.get("localizacao"),
                descricao_curta=startup.get("descricao_curta"),
                categoria=classif.get("categoria", "N/A"),
                confianca=float(classif.get("confianca", 0)),
                inception_fit_score=float(classif.get("inception_fit_score", 0)),
                wrapper_warning=bool(classif.get("risco_wrapper", False)),
                moat_score=float(classif.get("moat_score", 0)),
                evidencias_count=evidence.get("n_evidencias_validadas", 0) or 0,
                recomendacoes=recs_out,
            ))

        briefing_out = None
        if briefing_data:
            b = _dict(briefing_data)
            recs_b = []
            for r in b.get("recomendacoes", []) or []:
                r = _dict(r)
                try:
                    recs_b.append(RecommendationItem(**r))
                except Exception:
                    pass
            briefing_out = BriefingResponse(
                empresa=b.get("empresa", ""),
                setor=b.get("setor", "N/A"),
                maturidade_ai=b.get("maturidade_ai", "N/A"),
                score_maturidade=float(b.get("score_maturidade", 0)),
                inception_fit_score=float(b.get("inception_fit_score", 0)),
                wrapper_warning=bool(b.get("risco_wrapper", False)),
                fit_breakdown=b.get("fit_breakdown", {}),
                criterio_selecao=b.get("criterio_selecao", ""),
                nurture_suggestion=b.get("nurture_suggestion", ""),
                recomendacoes=recs_b,
                proximos_comerciais=b.get("proximos_comerciais", []) or [],
                proximos_tecnicos=b.get("proximos_tecnicos", []) or [],
                proximos_comunitarios=b.get("proximos_comunitarios", []) or [],
                fontes_consultadas=b.get("fontes_consultadas", []) or [],
                fontes_rag=b.get("fontes_rag", []) or [],
                generated_at=b.get("generated_at", "") or "",
                evidencia_insuficiente=bool(b.get("evidencia_insuficiente", False)),
            )

        qr = _dict(query_result)
        return {
            "startups": startups_out,
            "briefing": briefing_out,
            "query_keywords": qr.get("keywords", []) or [],
            "total_found": len(retrieved_startups),
        }

    @_app.post("/query", response_model=QueryResponse)
    async def query(req: QueryRequest):
        """Executa o pipeline multi-agente e monta a resposta com startups e briefing."""
        try:
            payload = await _build_query_payload(req)
            return QueryResponse(**payload)
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @_app.post("/query/export")
    async def query_export(req: QueryRequest):
        """Executa o pipeline e retorna o briefing completo como download JSON.

        O frontend oferece exportação 1-click (download .json) e o usuário pode
        imprimir em PDF via Ctrl+P (TAPI §6 diferencial — briefing exportável).
        """
        try:
            payload = await _build_query_payload(req)
            response_payload = QueryResponse(**payload).model_dump(mode="json")
            filename = "briefing_nvidia_radar.json"
            return Response(
                content=json.dumps(response_payload, ensure_ascii=False, indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            logger.error(f"Query export failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    # ---- Candidates ----

    @_app.post("/candidates", response_model=CandidateResponse)
    async def create_candidate(body: CandidateCreate):
        """Cria um candidato (upsert por startup_id) e retorna o registro completo."""
        next_date = None
        if body.next_action_date:
            try:
                next_date = date.fromisoformat(body.next_action_date)
            except ValueError:
                next_date = None
        pool = await _pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO candidates (
                       startup_id, notes, assigned_to, inception_fit_score,
                       categoria_ai, wrapper_warning, moat_score, tech_score,
                       sector_score, traction_score, nurture_cadence,
                       next_action_date, next_action_type, next_action_desc
                   )
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                   ON CONFLICT (startup_id) DO UPDATE
                   SET notes = EXCLUDED.notes,
                       assigned_to = EXCLUDED.assigned_to,
                       inception_fit_score = EXCLUDED.inception_fit_score,
                       categoria_ai = EXCLUDED.categoria_ai,
                       wrapper_warning = EXCLUDED.wrapper_warning,
                       moat_score = EXCLUDED.moat_score,
                       tech_score = EXCLUDED.tech_score,
                       sector_score = EXCLUDED.sector_score,
                       traction_score = EXCLUDED.traction_score,
                       nurture_cadence = EXCLUDED.nurture_cadence,
                       next_action_date = EXCLUDED.next_action_date,
                       next_action_type = EXCLUDED.next_action_type,
                       next_action_desc = EXCLUDED.next_action_desc,
                       updated_at = NOW()
                   RETURNING *""",
                body.startup_id, body.notes, body.assigned_to, body.inception_fit_score,
                body.categoria_ai, body.wrapper_warning, body.moat_score,
                body.tech_score, body.sector_score, body.traction_score,
                body.nurture_cadence, next_date, body.next_action_type,
                body.next_action_desc,
            )
            startup = await conn.fetchval(
                "SELECT nome FROM startups WHERE id = $1", body.startup_id
            )
        await pool.close()
        return _candidate_row(dict(row), startup)

    @_app.get("/candidates", response_model=list[CandidateResponse])
    async def list_candidates(
        status: str | None = None,
        categoria_ai: str | None = None,
        assigned_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """Lista candidatos com filtros, ordenados por Inception fit score (decrescente)."""
        pool = await _pool()
        async with pool.acquire() as conn:
            where, params, p = ["1=1"], [], 1
            if status:
                where.append(f"status = ${p}")
                params.append(status)
                p += 1
            if categoria_ai:
                where.append(f"categoria_ai = ${p}")
                params.append(categoria_ai)
                p += 1
            if assigned_to:
                where.append(f"assigned_to = ${p}")
                params.append(assigned_to)
                p += 1
            where_sql = " AND ".join(where)
            rows = await conn.fetch(
                f"""SELECT c.*, s.nome as startup_nome
                   FROM candidates c
                   JOIN startups s ON s.id = c.startup_id
                   WHERE {where_sql}
                   ORDER BY c.inception_fit_score DESC
                   LIMIT ${p} OFFSET ${p+1}""",
                *params, limit, offset,
            )
        await pool.close()
        return [_candidate_row(dict(r), r.get("startup_nome")) for r in rows]

    @_app.get("/candidates/{candidate_id}", response_model=CandidateResponse)
    async def get_candidate(candidate_id: int):
        """Busca um candidato pelo ID (404 se não existir)."""
        pool = await _pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT c.*, s.nome as startup_nome
                   FROM candidates c
                   JOIN startups s ON s.id = c.startup_id
                   WHERE c.id = $1""", candidate_id,
            )
        await pool.close()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return _candidate_row(dict(row), row.get("startup_nome"))

    @_app.patch("/candidates/{candidate_id}", response_model=CandidateResponse)
    async def update_candidate(candidate_id: int, body: CandidateUpdate):
        """Atualiza campos do candidato (somente os enviados) e retorna o registro."""
        pool = await _pool()
        updates, params, p = [], [], 1
        for field, value in body.model_dump(exclude_unset=True).items():
            if field == "next_action_date" and value:
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    value = None
            updates.append(f"{field} = ${p}")
            params.append(value)
            p += 1
        if updates:
            updates.append("updated_at = NOW()")
            params.append(candidate_id)
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""UPDATE candidates SET {', '.join(updates)}
                        WHERE id = ${p} RETURNING *""",
                    *params,
                )
                startup = await conn.fetchval(
                    "SELECT nome FROM startups WHERE id = $1", row["startup_id"]
                )
        else:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM candidates WHERE id = $1", candidate_id,
                )
                startup = await conn.fetchval(
                    "SELECT nome FROM startups WHERE id = $1", row["startup_id"]
                )
        await pool.close()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return _candidate_row(dict(row), startup)

    @_app.delete("/candidates/{candidate_id}")
    async def delete_candidate(candidate_id: int):
        """Remove um candidato e informa se houve exclusão (true/false)."""
        pool = await _pool()
        async with pool.acquire() as conn:
            r = await conn.execute(
                "DELETE FROM candidates WHERE id = $1", candidate_id,
            )
        await pool.close()
        return {"deleted": r != "DELETE 0"}

    # ---- Nurture log ----

    @_app.post("/candidates/{candidate_id}/nurture", response_model=NurtureLogResponse)
    async def add_nurture(candidate_id: int, body: NurtureLogEntry):
        """Registra ação de nurture e atualiza last_contacted_at/type conforme desfecho."""
        pool = await _pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO nurture_log (candidate_id, action_type, channel, outcome, notes)
                   VALUES ($1, $2, $3, $4, $5)
                   RETURNING *""",
                candidate_id, body.action_type, body.channel,
                body.outcome, body.notes,
            )
            if body.outcome == "positive":
                await conn.execute(
                    """UPDATE candidates
                       SET last_contacted_at = NOW(), last_contacted_type = $2,
                           updated_at = NOW()
                       WHERE id = $1""",
                    candidate_id, body.action_type,
                )
            elif body.outcome == "scheduled":
                await conn.execute(
                    """UPDATE candidates
                       SET last_contacted_at = NOW(), updated_at = NOW()
                       WHERE id = $1""",
                    candidate_id,
                )
        await pool.close()
        return NurtureLogResponse(
            id=row["id"],
            candidate_id=row["candidate_id"],
            action_type=row["action_type"],
            channel=row["channel"],
            outcome=row["outcome"],
            notes=row["notes"],
            created_at=str(row["created_at"]) if row.get("created_at") else None,
        )

    @_app.get("/nurture/upcoming")
    async def nurture_upcoming(
        days: int = Query(default=7, ge=1, le=90),
    ):
        """Lista candidatos com próxima ação de nurture dentro de `days` dias."""
        pool = await _pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT c.*, s.nome as startup_nome
                   FROM candidates c
                   JOIN startups s ON s.id = c.startup_id
                   WHERE c.next_action_date <= (CURRENT_DATE + $1::int)
                     AND c.status NOT IN ('declined', 'onboarding')
                   ORDER BY c.next_action_date ASC
                   LIMIT 50""",
                days,
            )
        await pool.close()
        return [
            _candidate_row(dict(r), r.get("startup_nome"))
            for r in rows
        ]

    @_app.get("/candidates/{candidate_id}/nurture", response_model=list[NurtureLogResponse])
    async def get_nurture_log(candidate_id: int):
        """Retorna o histórico de nurture de um candidato (mais recente primeiro)."""
        pool = await _pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM nurture_log WHERE candidate_id = $1 ORDER BY created_at DESC",
                candidate_id,
            )
        await pool.close()
        return [
            NurtureLogResponse(
                id=r["id"],
                candidate_id=r["candidate_id"],
                action_type=r["action_type"],
                channel=r["channel"],
                outcome=r["outcome"],
                notes=r["notes"],
                created_at=str(r["created_at"]) if r.get("created_at") else None,
            )
            for r in rows
        ]

    return _app


def _dict(v):
    """Converte objetos variados (dict, dataclass, SQLRow) em dict simples."""
    if isinstance(v, dict):
        return v
    if hasattr(v, "__dict__"):
        return v.__dict__
    if hasattr(v, "_row"):
        return dict(v)
    return {}


def _candidate_row(row: dict, startup_nome: str | None) -> CandidateResponse:
    """Mapeia uma linha do PostgreSQL para o schema CandidateResponse."""
    return CandidateResponse(
        id=row.get("id", 0),
        startup_id=row.get("startup_id", 0),
        startup_nome=startup_nome,
        inception_fit_score=float(row.get("inception_fit_score") or 0),
        status=row.get("status", "identificado"),
        categoria_ai=row.get("categoria_ai", "desconhecido"),
        wrapper_warning=bool(row.get("wrapper_warning", False)),
        fit_justification=row.get("fit_justification"),
        moat_score=float(row.get("moat_score") or 0),
        tech_score=float(row.get("tech_score") or 0),
        sector_score=float(row.get("sector_score") or 0),
        traction_score=float(row.get("traction_score") or 0),
        nurture_cadence=row.get("nurture_cadence", "mensal"),
        next_action_date=str(row["next_action_date"]) if row.get("next_action_date") else None,
        next_action_type=row.get("next_action_type"),
        next_action_desc=row.get("next_action_desc"),
        notes=row.get("notes"),
        assigned_to=row.get("assigned_to"),
        last_contacted_at=str(row["last_contacted_at"]) if row.get("last_contacted_at") else None,
        last_contacted_type=row.get("last_contacted_type"),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
    )


app = get_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
