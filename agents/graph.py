"""LangGraph multi-agent pipeline.

Wires 9 agents into a state graph with a supervisor hub and back-edges.

Fluxo (TAPI §6):
  query_planner → retriever → extractor → classifier → evidence_validator
       ↓
     supervisor (hub central: monitora telemetria/evidência em tempo real)
       ├── nvidia_rag → recommendation → briefing → END   (sinais OK)
       ├── query_planner (replan: expande query)          (retrieval vazio/fraca)
       ├── retriever      (retry: limite ampliado)        (retriever lento)
       └── briefing       (degradação graciosa)           (orçamento esgotado)

  O supervisor é o nó central: cada nó retorna a ele quando decide, e ele
  roteia para frente ou para trás. Contadores de orçamento no estado
  (replan_count, retry_count) e a latência do retriever (telemetria) guiam a
  decisão, garantindo terminação dos laços. Quando a maioria das evidências é
  inválida, o supervisor marca state.low_evidence=True e o nó nvidia_rag pula
  o RAG externo (Cohere/Qdrant), completando o briefing com aviso explícito.
"""
from __future__ import annotations

import inspect
import time as _time
import uuid as _uuid
from collections.abc import Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from loguru import logger

from agents.nodes.briefing import briefing
from agents.nodes.classifier import classifier
from agents.nodes.evidence_validator import evidence_validator
from agents.nodes.extractor import extractor
from agents.nodes.nvidia_rag import nvidia_rag
from agents.nodes.query_planner import query_planner
from agents.nodes.recommendation import recommendation
from agents.nodes.retriever import retriever
from agents.nodes.supervisor import route_supervisor, supervisor
from agents.state import AgentState


def _instrument_node(name: str, node: Callable) -> Callable:
    """Wrap a graph node to time/count its execution into state.telemetry.

    Handles both sync (e.g. supervisor helper paths) and async node functions.
    Recovery por nó: uma exceção não derruba o pipeline — registra em
    state.errors, sinaliza degradação graciosa (next_agent=briefing) e
    continua com o estado preservado (TAPI §6: resiliência operacional).
    O nó briefing NUNCA é engolido: é a última rede de segurança do grafo.
    """
    async def wrapped(state: AgentState) -> AgentState:
        """Executa o nó registrando tempo, contagem e recuperação de erro."""
        t0 = _time.perf_counter()
        try:
            out = node(state)
            if inspect.isawaitable(out):
                out = await out
        except Exception as e:  # noqa: BLE001 — recovery deliberado por nó
            if name == "briefing":
                raise
            state.errors = list(state.errors or []) + [f"[{name}] {type(e).__name__}: {e}"]
            logger.warning(f"[graph] erro no nó {name}: {e} — degradando graciosamente")
            state.next_agent = "briefing"
            out = state
        finally:
            dt = (_time.perf_counter() - t0) * 1000
            if state.telemetry is not None:
                state.telemetry.node_timings[name] = \
                    state.telemetry.node_timings.get(name, 0.0) + dt
                state.telemetry.node_counts[name] = \
                    state.telemetry.node_counts.get(name, 0) + 1
        return out
    return wrapped


def build_graph():
    """Build the LangGraph with 9 agents + 1 supervisor hub.

    Fluxo:
      linear até evidence_validator; em seguida o supervisor (hub) decide:
      nvidia_rag (segue), query_planner/retriever (back-edges de recurso) ou
      briefing (degradação graciosa). Back-edges são limitados por contadores
      de orçamento no estado, garantindo terminação.
    """
    g = StateGraph(AgentState)

    # 9 nós de agentes, todos envelopados para telemetria por nó
    for node_name, node_fn in [
        ("query_planner", query_planner),
        ("retriever", retriever),
        ("extractor", extractor),
        ("classifier", classifier),
        ("evidence_validator", evidence_validator),
        ("supervisor", supervisor),
        ("nvidia_rag", nvidia_rag),
        ("recommendation", recommendation),
        ("briefing", briefing),
    ]:
        g.add_node(node_name, _instrument_node(node_name, node_fn))

    # Explicito: fluxo linear até o hub do supervisor
    g.set_entry_point("query_planner")
    g.add_edge("query_planner", "retriever")
    g.add_edge("retriever", "extractor")
    g.add_edge("extractor", "classifier")
    g.add_edge("classifier", "evidence_validator")
    g.add_edge("evidence_validator", "supervisor")

    # SUPERVISOR HUB: decisão dinâmica (continue / replan / retry / graceful end)
    g.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "nvidia_rag": "nvidia_rag",
            "query_planner": "query_planner",
            "retriever": "retriever",
            "briefing": "briefing",
        },
    )

    # Fluxo de conclusão
    g.add_edge("nvidia_rag", "recommendation")
    g.add_edge("recommendation", "briefing")
    g.add_edge("briefing", END)

    # Checkpointer em memória (TAPI §6 resiliência): permite checkpoint/resume
    # por run via thread_id. Cada consulta usa um thread_id novo (run_pipeline).
    return g.compile(checkpointer=MemorySaver())


pipeline = build_graph()


async def run_pipeline(user_query: str) -> AgentState:
    """Run the full pipeline for a user query.

    LangGraph's ainvoke returns the final state as a dict (one entry per
    channel of AgentState); the telemetry object is preserved by reference.
    """
    initial_state = AgentState(user_query=user_query, next_agent="query_planner")
    initial_state.telemetry.run_id = _uuid.uuid4().hex[:12]
    initial_state.telemetry.started_at = _time.time()
    # Thread_id novo por consulta: o MemorySaver (checkpointer) isola o estado
    # entre runs e habilita checkpoint/resume sem colisão entre requisições.
    result = await pipeline.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": _uuid.uuid4().hex}},
    )

    tel = result.get("telemetry")
    if tel is not None:
        tel.ended_at = _time.time()
        tel.low_evidence = bool(result.get("low_evidence", False))

    # Persist telemetry (single small NDJSON append; ~µs, deterministic).
    try:
        from agents.observability import submit_result
        await submit_result(result)
    except Exception:
        pass
    return result


def run_sync(user_query: str) -> AgentState:
    """Synchronous wrapper using asyncio.run."""
    import asyncio
    return asyncio.run(run_pipeline(user_query))
