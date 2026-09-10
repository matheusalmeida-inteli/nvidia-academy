"""Testes do Supervisor Node (hub central com back-edges).

Valida:
1. decide_next puro: fluxo normal → nvidia_rag
2. retriever vazio → replan (query_planner), limitado por MAX_REPLANS
3. baixa evidência (>50% inválidos) → replan
4. retriever lento → retry (com limite ampliado em retriever_limit)
5. orçamento esgotado sem resultados → briefing gracioso
6. supervisor node: muta estado corretamente e registra supervisor_actions
7. baixa evidência marca state.low_evidence (semântica preservada)
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.state import AgentState, Telemetry
from agents.nodes.supervisor import (
    supervisor,
    decide_next,
    MAX_REPLANS,
    MAX_RETRIES,
)


def _state(**kwargs) -> AgentState:
    return AgentState(telemetry=Telemetry(), **kwargs)


@pytest.fixture
def good_state():
    return _state(
        evidence_results=[{"valido": True}, {"valido": True}],
        retrieved_startups=[{"id": 1}, {"id": 2}],
    )


def test_fluxo_normal_rota_nvidia_rag(good_state):
    assert decide_next(good_state) == "nvidia_rag"


def test_retriever_vazio_replan_primeira_vez():
    s = _state(retrieved_startups=[])
    assert decide_next(s) == "query_planner"


def test_replan_limitado_por_orcamento():
    s = _state(retrieved_startups=[], replan_count=MAX_REPLANS)
    assert decide_next(s) == "briefing"


def test_baixa_evidencia_dispara_replan():
    s = _state(
        evidence_results=[{"valido": False}, {"valido": False}, {"valido": True}],
        retrieved_startups=[{"id": 1}],
    )
    assert decide_next(s) == "query_planner"


def test_baixa_evidencia_orcamento_esgotado_segue_normal():
    s = _state(
        evidence_results=[{"valido": False}, {"valido": False}],
        retrieved_startups=[{"id": 1}],
        replan_count=MAX_REPLANS,
    )
    assert decide_next(s) == "nvidia_rag"


def test_retriever_lento_dispara_retry():
    s = _state(
        retrieved_startups=[{"id": 1}],
        evidence_results=[{"valido": True}],
    )
    s.telemetry.node_timings["retriever"] = 6000.0
    assert decide_next(s) == "retriever"


def test_retry_limitado_por_orcamento():
    s = _state(retrieved_startups=[{"id": 1}], retry_count=MAX_RETRIES)
    s.telemetry.node_timings["retriever"] = 6000.0
    assert decide_next(s) == "nvidia_rag"


def test_orcamento_esgotado_sem_startups_briefing_gracioso():
    s = _state(retrieved_startups=[], replan_count=MAX_REPLANS)
    assert decide_next(s) == "briefing"


def test_supervisor_node_marca_low_evidence():
    s = _state(
        evidence_results=[{"valido": False}, {"valido": False}],
        retrieved_startups=[{"id": 1}],
        replan_count=MAX_REPLANS,
    )
    out = __import__("asyncio").run(supervisor(s))
    assert out.low_evidence is True
    assert out.next_agent == "nvidia_rag"
    assert out.supervisor_actions  # trilha de auditoria preenchida


def test_supervisor_node_replan_incrementa_contador_e_expande_query():
    s = _state(retrieved_startups=[])
    out = __import__("asyncio").run(supervisor(s))
    assert out.next_agent == "query_planner"
    assert out.replan_count == 1
    assert out.expand_query is True
    assert any("replan" in a for a in out.supervisor_actions)


def test_supervisor_node_retry_amplia_limite():
    s = _state(retrieved_startups=[{"id": 1}])
    s.telemetry.node_timings["retriever"] = 6000.0
    out = __import__("asyncio").run(supervisor(s))
    assert out.next_agent == "retriever"
    assert out.retry_count == 1
    assert out.retriever_limit >= 50


def test_route_supervisor_delegates_next_agent():
    from agents.nodes.supervisor import route_supervisor
    s = _state(next_agent="query_planner")
    assert route_supervisor(s) == "query_planner"
    s2 = _state()
    assert route_supervisor(s2) == "nvidia_rag"