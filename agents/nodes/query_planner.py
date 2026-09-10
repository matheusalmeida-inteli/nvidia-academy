"""Agent 1: Query Planner.

Translates natural-language query into structured search criteria
and defines strategy for the retrieval agent.
"""
from __future__ import annotations

import re

from loguru import logger

from agents.llm import llm
from agents.state import AgentState, QueryResult

SECTOR_KEYWORDS = {
    "fintech": ["fintech", "financeiro", "banco", "pagamento", "crédito", "investimento", "conta digital"],
    "healthtech": ["saúde", "health", "médic", "hospital", "clínic", "healthcare", "diagnóstico"],
    "edtech": ["educação", "ensino", "escola", "edtech", "cursos", "aprendizado"],
    "proptech": ["imóvel", "proptech", "real estate", "aluguel", "imobiliári"],
    "agtech": ["agr", "agronegócio", "fazenda", "agro", "colheita", "safra"],
    "logística": ["logística", "delivery", "entrega", "frete", "transporte"],
    "retail": ["varejo", "e-commerce", "ecommerc", "loja", "compra"],
    "martech": ["marketing", "martech", "ads", "publicidade"],
    "iot": ["iot", "industria", "manufatura", "industrial"],
    "hrtech": ["rh", "recrutamento", "hiring", "pessoas", "recursos humanos"],
    "cybersec": ["cibersegurança", "segurança", "cyber", "security", "antifraude"],
    "foodtech": ["comida", "alimento", "food", "restaurante", "ifood"],
    "games": ["game", "jogo", "games"],
    "speech": ["voz", "fala", "speech", "asr", "tts", "áudio"],
    "ai": ["ai", "ia", "inteligência artificial", "generativa", "llm", "machine learning"],
}

STAGE_KEYWORDS = {
    "pre-seed": ["pre-seed", "pre seed", "inicial"],
    "seed": ["seed"],
    "serie_a": ["série a", "serie a", "series a"],
    "serie_b": ["série b", "serie b", "series b"],
    "serie_c": ["série c", "serie c", "series c"],
}


def heuristic_parse(query: str) -> QueryResult:
    """Rule-based parsing when LLM is not available."""
    q = query.lower()
    keywords = []
    filters = {}

    # Sector detection
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(kw in q for kw in kws):
            filters["setor"] = sector
            keywords.append(sector)
            break

    # Stage detection
    for stage, kws in STAGE_KEYWORDS.items():
        if any(kw in q for kw in kws):
            filters["estagio"] = stage
            break

    # AI-related queries
    if any(kw in q for kw in ["ai", "ia", "inteligência artificial", "generativa", "llm", "machine learning"]):
        filters["ai_focus"] = True
        keywords.extend(["ai", "ml", "llm"])

    # Generic keyword extraction
    words = re.findall(r"\b[a-zà-ÿ]{4,}\b", q)
    stopwords = {"sobre", "para", "com", "que", "uma", "uns", "como", "aqui", "ali", "todas", "todos", "empresas", "startup", "startups", "brasileiras", "brasil", "análise", "recomendação", "tech", "tecnologia", "tecnologias"}
    keywords.extend([w for w in words if w not in stopwords][:5])

    if not keywords:
        # Sem tokens com 4+ chars além de stopwords: usa os próprios termos da
        # query (qualquer tamanho) em vez de mascarar com ["startup","ai","brasil"].
        raw_tokens = [w for w in re.findall(r"\b[a-zà-ÿ]{2,}\b", q) if w not in stopwords]
        keywords = raw_tokens if raw_tokens else ["nvidia"]

    return QueryResult(
        raw_query=query,
        keywords=list(set(keywords)),
        filters=filters,
        strategy="ai_focused" if filters.get("ai_focus") else "general",
    )


async def query_planner(state: AgentState) -> AgentState:
    """Plan a query: extract keywords, filters, strategy."""
    query = state.user_query
    logger.info(f"[query_planner] Processing: {query[:60]}")

    # REPLAN (filhos do supervisor): expandir a query removendo filtros
    # restritivos e usando keywords genéricas, para ampliar a cobertura.
    if getattr(state, "expand_query", False):
        state.expand_query = False  # consome o sinal (uma expansão por replan)
        qr = heuristic_parse(query)
        # Remove filtros que restringem o recorte (setor/estagio/ai_focus)
        qr.filters = {}
        # Mantém apenas keywords genéricas de cobertura ampla
        qr.keywords = [k for k in qr.keywords if k not in ("ai", "ml", "llm")]
        qr.keywords = (qr.keywords or ["startup", "ia", "brasil"])[:8]
        qr.strategy = "broadened"
        state.query_result = qr
        state.retrieval_strategy = "broadened"
        state.next_agent = "retriever"
        logger.info(f"[query_planner] Replan: expanded query -> {qr.keywords}")
        return state

    if len(query) < 3:
        # Query too short - return minimal result
        state.query_result = QueryResult(
            raw_query=query,
            keywords=["startup", "ai", "brasil"],
            filters={},
            strategy="general",
        )
        state.next_agent = "retriever"
        logger.info("[query_planner] Query too short, using defaults")
        return state

    if llm.is_available():
        try:
            system = """You are a query planner for a startup analysis system.
Parse the user's query and return a JSON object with:
- keywords: list of relevant search terms
- filters: {setor?, estagio?, localizacao?, ai_focus?, porte?}
- strategy: 'ai_native_focus' | 'ai_enabled_focus' | 'general' | 'vertical_specific'

Return ONLY valid JSON."""

            user = f"Query: {query}"
            raw = await llm.complete(system, user, response_format={"type": "json_object"})
            # Telemetry: token usage + latency of this node's LLM call
            state.telemetry.node_token_usage["query_planner"] = llm.last_call_stats()

            import json
            try:
                data = json.loads(raw)
                keywords = data.get("keywords", [])
                # Sanitiza: LLM pode devolver lista vazia — cai p/ heurística
                # (evita SQL malformado `GREATEST(0, )` no retriever).
                if not isinstance(keywords, list) or not any(
                    str(k).strip() for k in keywords
                ):
                    raise ValueError("empty keywords")
                state.query_result = QueryResult(
                    raw_query=query,
                    keywords=[str(k) for k in keywords],
                    filters=data.get("filters", {}),
                    strategy=data.get("strategy", "general"),
                )
            except Exception:
                state.query_result = heuristic_parse(query)
        except Exception as e:
            logger.warning(f"LLM parse failed, using heuristic: {e}")
            state.query_result = heuristic_parse(query)
    else:
        state.query_result = heuristic_parse(query)

    state.next_agent = "retriever"
    logger.info(f"[query_planner] keywords={state.query_result.keywords}, filters={state.query_result.filters}")
    return state
