"""Agent 5: Evidence Validator.

Valida que as classificações tenham suporte em evidências/documentos.
Retorna confidence score, lacunas e quais documentos contam como evidência
verificada (peso por tipo de documento).
"""
from __future__ import annotations

from loguru import logger

from agents.state import AgentState
from scraper.config.settings import get_settings
from scraper.pipelines.loaders import DatabaseLoader

# Peso por tipo de documento na evidência: documentos que carregam sinal de
# AI/stack (vaga, perfil de founder, release, careers) pesam mais que notícia.
DOC_WEIGHTS = {
    "vaga": 1.0,
    "perfil_founder": 1.0,
    "release": 0.9,
    "careers": 0.9,
    "site_institucional": 0.8,
    "linkedin": 0.6,
    "noticia": 0.5,
    "blog": 0.5,
    "outro": 0.4,
    "": 0.4,
}
EVIDENCE_THRESHOLD = 0.7  # pct: pesos >= threshold contam como evidência verificada


def doc_weight(tipo) -> float:
    """Retorna o peso de evidência para um tipo de documento."""
    return DOC_WEIGHTS.get(str(tipo or "").lower(), 0.4)


async def evidence_validator(state: AgentState) -> AgentState:
    """Validate that classifications are supported by evidence."""
    profiles = state.extracted_profiles or []
    classifications = state.classifications or []
    settings = get_settings()

    evidence_results = []
    for profile, classification in zip(profiles, classifications, strict=True):
        nome = profile.get("nome", "")
        sid = None
        for s in state.retrieved_startups or []:
            if s.get("nome") == nome:
                sid = s.get("id")
                break

        docs = []
        try:
            if sid:
                async with DatabaseLoader(settings) as loader:
                    async with loader.pool.acquire() as conn:
                        rows = await conn.fetch(
                            "SELECT id, titulo, url_fonte, tipo, data_publicacao, source_meta FROM documentos WHERE startup_id = $1",
                            sid,
                        )
                        for row in rows:
                            docs.append(dict(row))
        except Exception as e:
            logger.debug(f"[evidence] DB error for {nome}: {e}")

        # Validate
        n_docs = len(docs)
        n_ai_signals = len(profile.get("sinais_ai", []))

        # Evidências verificadas: docs com peso >= threshold (não é contagem
        # crua de documentos — cada tipo tem relevância própria).
        evidencias_validas = [
            d for d in docs if doc_weight(d.get("tipo")) >= EVIDENCE_THRESHOLD
        ]
        n_validas = len(evidencias_validas)

        # Score considera a quantidade de evidências verificadas (peso real)
        # e não apenas o total de docs armazenado.
        evidence_score = min(
            1.0,
            (n_validas / 3.0) * 0.5 + (n_ai_signals / 5.0) * 0.4 + 0.1,
        )
        if n_validas == 0 and n_docs > 0:
            evidence_score = min(evidence_score, 0.3)
        valido = (n_validas >= 1 or n_docs >= 1) and evidence_score > 0.3

        lacunas = []
        if n_validas < 3:
            lacunas.append(
                f"Apenas {n_validas} evidências verificadas (mínimo 3 para alta confiança)"
            )
        if n_docs > 0 and n_validas == 0:
            lacunas.append("Documentos existentes não carregam sinais diretos de AI/stack")
        if not profile.get("sinais_ai") and classification["categoria"] != "non_ai":
            lacunas.append("Poucos sinais de AI nos documentos")

        evidence_results.append({
            "nome": nome,
            "valido": valido,
            "evidencias": [
                {
                    "titulo": d["titulo"],
                    "url": d["url_fonte"],
                    "tipo": d["tipo"],
                    "valida": doc_weight(d.get("tipo")) >= EVIDENCE_THRESHOLD,
                }
                for d in docs[:5]
            ],
            "n_evidencias_validadas": n_validas,
            "lacunas": lacunas,
            "confianca": round(evidence_score, 2),
        })

        # Consolidated faithfulness/evidence reason for telemetry
        state.telemetry.evidence_reasons[nome] = (
            "ok" if valido else "insufficient_evidence"
        )

    state.evidence_results = evidence_results
    state.next_agent = "nvidia_rag"
    logger.info(f"[evidence_validator] Validated {sum(1 for e in evidence_results if e['valido'])}/{len(evidence_results)} startups")
    return state
