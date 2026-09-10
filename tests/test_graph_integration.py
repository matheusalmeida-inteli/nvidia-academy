"""Testes de integração do grafo completo (grafo real com nós de infra mockados).

Valida o fluxo fim-a-fim pelo pipeline LangGraph compilado, com os nós que
tocam Postgres/Qdrant/LLM substituídos por stubs determinísticos:

1. Fluxo nominal: retriever retorna startups → supervisor roteia p/ nvidia_rag
   → recommendations → briefing; supervisor_actions em EN, 1 chamada/nó.
2. Replan limitado: retriever retorna vazio → supervisor vai a query_planner
   (expande) 2x → briefing gracioso; grafo termina sem laço infinito.
3. Contagem de nós no replan reflete back-edges (query_planner/retriever 3x).
4. Supervisor presente no hub e grafo compila com 9 nós + __start__.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agents.graph as graph_mod
from agents.state import AgentState


def _stub_retriever(startups):
    async def _retriever(state: AgentState) -> AgentState:
        state.retrieved_startups = [dict(s) for s in startups] if startups else []
        state.retrieval_strategy = "keyword_match"
        state.next_agent = "extractor"
        return state
    return _retriever


def _stub_extractor(state: AgentState) -> AgentState:
    state.extracted_profiles = [
        {"nome": s["nome"], "setor": s.get("setor", ""), "sinais_ai": ["llm"]}
        for s in state.retrieved_startups or []
    ]
    state.next_agent = "classifier"
    return state


def _stub_classifier(state: AgentState) -> AgentState:
    state.classifications = [
        {
            "nome": p["nome"],
            "categoria": "ai_native",
            "confianca": 0.9,
            "risco_wrapper": False,
            "moat_score": 3.0,
            "inception_fit_score": 0.7,
            "fit_breakdown": {},
        }
        for p in state.extracted_profiles or []
    ]
    state.next_agent = "evidence_validator"
    return state


def _stub_evidence_validator(state: AgentState) -> AgentState:
    state.evidence_results = [
        {"nome": p["nome"], "valido": True, "evidencias": [], "lacunas": [], "confianca": 0.8}
        for p in state.extracted_profiles or []
    ]
    state.next_agent = "supervisor"
    return state


async def _stub_nvidia_rag(state: AgentState) -> AgentState:
    # Referências determinísticas: integram o grafo sem depender de Qdrant/DB.
    # O retriever real é tentado (bônus), mas o fallback fixo garante
    # `low_evidence=False` no fluxo nominal em qualquer ambiente.
    _FALLBACK_REFS = [
        {"title": "NVIDIA Inception for AI startups",
         "content": "GPU credits and go-to-market support para startups de IA.",
         "tech": "NVIDIA Inception", "url": "https://nvda.ws/inception", "score": 0.81,
         "category": "program"},
        {"title": "NVIDIA NIM microservices",
         "content": "Inferência de LLMs otimizada em GPUs NVIDIA.",
         "tech": "NVIDIA NIM", "url": "https://nvda.ws/nim", "score": 0.77,
         "category": "inference"},
    ]
    try:
        import os
        os.environ["COHERE_API_KEY"] = ""
        from rag.retrieval.retriever import HybridRetriever
        retriever = HybridRetriever()
        refs = await retriever.retrieve(state.user_query or "nvidia ai startup", top_k_rerank=2)
        if len(refs) >= 2:
            state.nvidia_references = refs[:5]
            state.low_evidence = False
        else:
            state.nvidia_references = _FALLBACK_REFS
            state.low_evidence = False
    except Exception:
        state.nvidia_references = _FALLBACK_REFS
        state.low_evidence = False
    state.next_agent = "recommendation"
    return state


def _stub_recommendation(state: AgentState) -> AgentState:
    state.recommendations = [
        {
            "nome": p["nome"],
            "categoria": c.get("categoria", "unknown"),
            "confianca": c.get("confianca", 0),
            "risco_wrapper": c.get("risco_wrapper", False),
            "moat_score": c.get("moat_score", 0),
            "inception_fit_score": c.get("inception_fit_score", 0),
            "fit_breakdown": c.get("fit_breakdown", {}),
            "recomendacoes": [],
            "community_actions": [],
        }
        for p, c in zip(state.extracted_profiles or [], state.classifications or [])
    ]
    state.next_agent = "briefing"
    return state


def _build_patched(startups, monkeypatch) -> "graph_mod.pipeline":
    """Configura stubs e compila o grafo com o retriever determinístico escolhido."""
    monkeys = {
        "retriever": _stub_retriever(startups),
        "extractor": _stub_extractor,
        "classifier": _stub_classifier,
        "evidence_validator": _stub_evidence_validator,
        "nvidia_rag": _stub_nvidia_rag,
        "recommendation": _stub_recommendation,
    }
    for name, fn in monkeys.items():
        monkeypatch.setattr(graph_mod, name, fn)
    return graph_mod.build_graph()


def _run(graph, query: str):
    initial = AgentState(user_query=query, next_agent="query_planner")
    initial.telemetry.run_id = "test-integration"
    # O grafo usa checkpointer MemorySaver → thread_id obrigatório por run.
    return asyncio.run(
        graph.ainvoke(
            initial,
            config={"configurable": {"thread_id": "test-integration"}},
        )
    )


def test_fluxo_nominal_completo(monkeypatch):
    graph = _build_patched([{"id": 1, "nome": "StubCo", "setor": "fintech"}], monkeypatch)
    result = _run(graph, "startup de fintech")

    assert len(result["retrieved_startups"]) == 1
    assert len(result["recommendations"]) == 1
    assert result["supervisor_actions"] == ["nominal flow: signals OK"]
    assert result["low_evidence"] is False
    assert "Nenhuma" not in str(result["briefing"])
    assert result["telemetry"].node_counts["supervisor"] == 1


def test_replan_limitado_termina_em_briefing_gracioso(monkeypatch):
    graph = _build_patched([], monkeypatch)
    result = _run(graph, "gigante de blockchain quantico")

    actions = result["supervisor_actions"]
    assert any(a.startswith("replan #") for a in actions)
    assert actions[-1].endswith("budget exhausted without results")
    assert len(result["retrieved_startups"]) == 0
    assert len(result["recommendations"]) == 0
    assert "Nenhuma startup encontrada" in str(result["briefing"])


def test_back_edges_contagem_de_nos(monkeypatch):
    graph = _build_patched([], monkeypatch)
    result = _run(graph, "termo sem resultado")

    counts = result["telemetry"].node_counts
    # query_planner e retriever rodam 1x nominal + 2x replans = 3
    assert counts["query_planner"] == 3
    assert counts["retriever"] == 3
    assert counts["supervisor"] == 3
    assert counts["briefing"] == 1
    assert "nvidia_rag" not in counts
    assert result["expand_query"] is False  # sinal consumido pelo query_planner


def test_graph_compila_com_supervisor_no_hub(monkeypatch):
    graph = _build_patched([{"id": 1, "nome": "X", "setor": "ai"}], monkeypatch)
    names = list(graph.nodes)
    assert "supervisor" in names
    assert "nvidia_rag" in names
    assert "briefing" in names
    assert len(names) == 10  # __start__ + 9 nós


def test_erro_em_no_degrada_com_estado_preservado(monkeypatch):
    """F4: exceção num nó não derruba o pipeline (recovery com state.errors)."""

    def _boom(state: AgentState) -> AgentState:
        raise RuntimeError("falha simulada no nó")

    # Stubs como em _build_patched, MAS classifier definido por último para
    # levantar exceção — build_graph captura a referência na compilação.
    monkeypatch.setattr(graph_mod, "retriever", _stub_retriever([]))
    monkeypatch.setattr(graph_mod, "extractor", _stub_extractor)
    monkeypatch.setattr(graph_mod, "evidence_validator", _stub_evidence_validator)
    monkeypatch.setattr(graph_mod, "nvidia_rag", _stub_nvidia_rag)
    monkeypatch.setattr(graph_mod, "recommendation", _stub_recommendation)
    monkeypatch.setattr(graph_mod, "classifier", _boom)
    graph = graph_mod.build_graph()
    result = _run(graph, "startup qualquer")

    assert "classifier" in str(result["errors"])
    assert result["briefing"] is not None
    # Replan roda 3x (idem teste de back-edges) e o erro é registrado em cada rodada
    assert result["telemetry"].node_counts.get("classifier") == 3
    assert len(result["errors"]) == 3