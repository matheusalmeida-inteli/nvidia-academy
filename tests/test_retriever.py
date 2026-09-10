"""Testes do retriever: geração de SQL de busca e ordenação por relevância."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.nodes.retriever import build_search_query


class QueryResultStub:
    def __init__(self, keywords, filters):
        self.keywords = keywords
        self.filters = filters


def test_sem_keywords_cai_em_1_mais_um():
    where, params, order = build_search_query(QueryResultStub([], {}))
    assert where == "1=1"
    assert params == []
    assert order == "id"  # sem malformar GREATEST(0, )


def test_keywords_geram_where_or_e_ordem_por_peso():
    where, params, order = build_search_query(QueryResultStub(["fintech"], {}))
    # condição OR sobre os 3 campos
    assert "nome" in where and "setor" in where and "descricao_curta" in where
    assert params == ["%fintech%"] * 3
    # peso nome 3.0 > setor 2.0 > descricao 1.0
    assert "3.0" in order and "2.0" in order and "1.0" in order
    assert order.endswith("DESC, id")


def test_filtro_de_setor_adiciona_param_separado():
    where, params, order = build_search_query(QueryResultStub(["ia"], {"setor": "saude"}))
    assert "LOWER(setor) LIKE $4" in where  # keyword usa 1..3, filtro usa $4
    assert params[-1] == "%saude%"


def test_multiplas_keywords_em_or_nao_and():
    where, params, order = build_search_query(
        QueryResultStub(["fintech", "llms"], {})
    )
    # keywords são OR entre si; filtros estruturados (se houver) são AND
    assert ") OR (" in where
    assert params == ["%fintech%"] * 3 + ["%llms%"] * 3
    assert order.endswith("DESC, id")


def test_keywords_or_e_filtro_and_juntos():
    where, params, order = build_search_query(
        QueryResultStub(["fintech"], {"setor": "fintech"})
    )
    assert ") AND " in where
    assert params[-1] == "%fintech%"