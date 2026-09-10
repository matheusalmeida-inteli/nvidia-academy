"""Agent 2: Retriever.

Queries the database (PostgreSQL) for startups matching the planner's
criteria. Combines structured filters with full-text search.
"""
from __future__ import annotations

from loguru import logger

from agents.state import AgentState
from scraper.config.settings import get_settings
from scraper.pipelines.loaders import DatabaseLoader

# Pesos por campo na relevância (nome > setor > descricao).
FIELD_WEIGHTS = {
    "nome": 3.0,
    "setor": 2.0,
    "descricao_curta": 1.0,
}


def build_search_query(query_result) -> tuple[str, list, str]:
    """Build parameterized SQL search from query result.

    Retorna (where_sql, params, order_sql). Keywords são unidas com OR
    (qualquer keyword casa, ranking por quantidade/peso), enquanto filtros
    estruturados (setor/estagio) permanecem em AND. O order_sql rankeia as
    startups pela soma dos pesos das keywords nos campos (nome > setor >
    descricao), quebrando empate por id.
    """
    where_clauses = []
    params = []
    score_terms = []

    keywords = query_result.keywords or []
    for kw in keywords:
        pattern = f"%{kw.lower()}%"
        field_conditions = []
        for field, weight in FIELD_WEIGHTS.items():
            params.append(pattern)
            score_terms.append(
                f"(CASE WHEN LOWER({field}) LIKE ${len(params)} THEN {weight} ELSE 0 END)"
            )
            field_conditions.append(f"LOWER({field}) LIKE ${len(params)}")
        where_clauses.append("(" + " OR ".join(field_conditions) + ")")

    filters = query_result.filters or {}
    filter_clauses = []
    if "setor" in filters:
        params.append(f"%{filters['setor'].lower()}%")
        filter_clauses.append(f"LOWER(setor) LIKE ${len(params)}")

    if "estagio" in filters:
        params.append(filters["estagio"])
        filter_clauses.append(f"estagio = ${len(params)}")

    parts = []
    if where_clauses:
        parts.append("(" + " OR ".join(where_clauses) + ")")
    if filter_clauses:
        parts.append(" AND ".join(filter_clauses))
    where_sql = " AND ".join(parts) if parts else "1=1"

    if score_terms:
        order_sql = "GREATEST(0, " + " + ".join(score_terms) + ") DESC, id"
    else:
        # Sem keywords (ex.: LLM respondeu com lista vazia): evita o SQL
        # malformado `GREATEST(0, )`; ordena por id com o filtro estruturado.
        order_sql = "id"
    return where_sql, params, order_sql


async def retriever(state: AgentState) -> AgentState:
    """Retrieve startups matching the query."""
    if state.query_result is None:
        state.errors.append("No query_result available")
        state.next_agent = "extractor"
        return state

    logger.info(f"[retriever] Searching with keywords: {state.query_result.keywords}")

    settings = get_settings()
    where_sql, params, order_sql = build_search_query(state.query_result)

    # LIMIT ampliável: o supervisor pode pedir retry com escopo maior
    limit = max(int(state.retriever_limit or 25), 1)

    sql = f"""
        SELECT id, nome, site, setor, estagio, localizacao,
               descricao_curta, ano_fundacao, tamanho_time
        FROM startups
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT {limit}
    """

    results = []
    try:
        async with DatabaseLoader(settings) as loader:
            async with loader.pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                for row in rows:
                    results.append(dict(row))
    except Exception as e:
        logger.error(f"[retriever] DB error: {e}")
        state.errors.append(f"DB error: {e}")

    state.retrieved_startups = results
    state.retrieval_strategy = "keyword_match"
    state.next_agent = "extractor"
    logger.info(f"[retriever] Found {len(results)} startups")
    return state
