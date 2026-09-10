"""Testes de validação de entrada (API) e utilidades de evidência."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.nodes.evidence_validator import doc_weight, EVIDENCE_THRESHOLD
from api.main import QueryRequest


class TestQueryRequestValidation:
    def test_aceita_query_valida(self):
        req = QueryRequest(query="startup de fintech")
        assert req.query == "startup de fintech"

    def test_strip_espacos(self):
        req = QueryRequest(query="  fintech ai  ")
        assert req.query == "fintech ai"

    def test_apenas_espacos_em_branco(self):
        with pytest.raises(ValueError):
            QueryRequest(query="    ")

    def test_query_vazia(self):
        with pytest.raises(ValueError):
            QueryRequest(query="")

    def test_max_startups_faixa(self):
        with pytest.raises(ValueError):
            QueryRequest(query="fintech", max_startups=0)
        with pytest.raises(ValueError):
            QueryRequest(query="fintech", max_startups=101)


class TestDocWeight:
    def test_pesos_por_tipo(self):
        # Sinais diretos de stack/contratação pesam mais que notícia
        assert doc_weight("vaga") >= EVIDENCE_THRESHOLD
        assert doc_weight("perfil_founder") >= EVIDENCE_THRESHOLD
        assert doc_weight("noticia") < EVIDENCE_THRESHOLD
        assert doc_weight("blog") < EVIDENCE_THRESHOLD

    def test_tipo_desconhecido_pesa_baixo(self):
        assert doc_weight(None) < EVIDENCE_THRESHOLD
        assert doc_weight("") < EVIDENCE_THRESHOLD
        assert doc_weight("desconhecido") < EVIDENCE_THRESHOLD