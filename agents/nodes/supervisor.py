"""Supervisor node — decision hub between linear stages (TAPI diferencial).

Monitora, em tempo real, sinais de qualidade do pipeline (cobertura do
retriever, latência, validação de evidências) e decide o próximo passo:

  * nvidia_rag      — sinais OK, segue o fluxo normal
  * query_planner   — replan: reescrever/expandir a query (back-edge)
  * retriever       — retry: nova busca com limite ampliado (back-edge)
  * briefing        — degradação graciosa quando o orçamento esgota

A decisão é pura (função `decide_next`) testável sem banco de dados.
Rate limiting via contadores de orçamento no estado (replan_count,
retry_count) garante terminação do laço.
"""
from __future__ import annotations

from loguru import logger

from agents.state import AgentState

# Budget de laço (garantem terminação)
MAX_REPLANS = 2
MAX_RETRIES = 1
# Latência do retriever (ms) que dispara retry ampliado
SLOW_RETRIEVER_MS = 4000.0
# Se >50% das startups têm evidência inválida, replan (senão segue p/ RAG)
LOW_EVIDENCE_RATIO = 0.5
# Fator de ampliação do LIMIT SQL no retry do retriever
RETRY_LIMIT_MULTIPLIER = 2.0


def _low_evidence_ratio(state: AgentState) -> float:
    """Fraction of evidence_results with valido=False."""
    results = state.evidence_results or []
    if not results:
        return 0.0
    invalid = sum(1 for e in results if not e.get("valido", False))
    return invalid / len(results)


def _retriever_latency_ms(state: AgentState) -> float:
    """Latência acumulada do retriever (telemetria do grafo)."""
    return state.telemetry.node_timings.get("retriever", 0.0)


def decide_next(state: AgentState) -> str:
    """Decide o próximo destino a partir dos sinais do estado/telemetria.

    Retorna uma das chaves: "nvidia_rag" | "query_planner" | "retriever" | "briefing".
    Lógica pura — não muta o estado (mutações ficam no nó `supervisor`).
    """
    n_startups = len(state.retrieved_startups or [])
    ratio = _low_evidence_ratio(state)
    latency = _retriever_latency_ms(state)

    # 1) Sem startups recuperadas e orçamento de replan → expandir query
    if n_startups == 0 and state.replan_count < MAX_REPLANS:
        return "query_planner"

    # 2) Baixa evidência (>50% inválidos) e orçamento de replan → replan
    if (
        state.evidence_results
        and ratio > LOW_EVIDENCE_RATIO
        and state.replan_count < MAX_REPLANS
    ):
        return "query_planner"

    # 3) Retriever lento e orçamento de retry → retry com limite ampliado
    if latency > SLOW_RETRIEVER_MS and state.retry_count < MAX_RETRIES:
        return "retriever"

    # 4) Orçamento esgotado sem startups → degradação graciosa (briefing)
    if n_startups == 0:
        return "briefing"

    # 5) Padrão: seguir o fluxo normal (nvidia_rag respeita state.low_evidence)
    return "nvidia_rag"


def route_supervisor(state: AgentState) -> str:
    """Roteia para o próximo destino decidido pelo supervisor."""
    return state.next_agent or "nvidia_rag"


async def supervisor(state: AgentState) -> AgentState:
    """Node central de supervisão: decide retry/replan/skip/briefing.

    Muta o estado com a decisão e registra a trilha de auditoria em
    `supervisor_actions` (persistida na telemetria). Marca também a flag
    `low_evidence` quando a maioria das evidências é inválida, mantendo a
    semântica original de nvidia_rag/briefing.
    """
    ratio = _low_evidence_ratio(state)
    # Recomputa o sinal a cada visita: um replan que recupera evidências
    # válidas precisa restaurar o fluxo normal (nvidia_rag/briefing usam a flag).
    state.low_evidence = bool(
        state.evidence_results and ratio > LOW_EVIDENCE_RATIO
    )
    if state.low_evidence:
        reason_low = f"{ratio:.0%} evidências inválidas — low_evidence=True"
        logger.info(f"[supervisor] {reason_low}")

    decision = decide_next(state)

    if decision == "query_planner":
        state.replan_count += 1
        state.expand_query = True
        state.next_agent = "query_planner"
        reason = f"replan #{state.replan_count}: {len(state.retrieved_startups or [])} startups, {ratio:.0%} invalid evidence"
    elif decision == "retriever":
        state.retry_count += 1
        state.retriever_limit = int(max(state.retriever_limit * RETRY_LIMIT_MULTIPLIER, 25))
        state.next_agent = "retriever"
        reason = f"retry #{state.retry_count}: slow retriever ({_retriever_latency_ms(state):.0f}ms), limit={state.retriever_limit}"
    elif decision == "briefing":
        state.next_agent = "briefing"
        reason = "graceful briefing: replan/retry budget exhausted without results"
    else:
        state.next_agent = "nvidia_rag"
        reason = "nominal flow: signals OK"

    state.supervisor_actions.append(reason)
    logger.info(f"[supervisor] decision={decision} — {reason}")
    return state
