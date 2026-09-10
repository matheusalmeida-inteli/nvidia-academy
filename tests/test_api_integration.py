"""Testes de integração do endpoint /query da API FastAPI."""

from fastapi.testclient import TestClient
import pytest

from api.main import get_app


class TestQueryIntegration:
    """Testes do endpoint /query com cobertura de sucesso, validação e fallback."""

    def setup_method(self):
        self.client = TestClient(get_app())

    def test_query_sucesso_sem_startups_no_fallback(self):
        """Query no modo fallback (sem Qdrant) retorna briefing válido."""
        resp = self.client.post(
            "/query",
            json={"query": "startup de fintech com IA", "max_startups": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        # O contrato deve ser respeitado independente de haver resultados
        assert "startups" in body
        assert "briefing" in body
        # Se não houver startups (sem BD), o briefing deve indicar a ausência
        if not body["startups"]:
            nurture = body["briefing"].get("nurture_suggestion", "")
            assert "Sem startups para nutrir" in nurture

    def test_query_vazia_retorna_422(self):
        """Query apenas com espaços retorna 422 com mensagem amigável."""
        resp = self.client.post(
            "/query",
            json={"query": "   ", "max_startups": 3},
        )
        assert resp.status_code == 422
        body = resp.json()
        # O corpo da erro vem como {'detail': [ {'type': 'value_error', 'msg': '...'} ]}
        detail = body["detail"]
        assert len(detail) > 0
        msg = detail[0].get("msg", "")
        # Verifica que a mensagem existe e indica erro de validação
        assert msg and isinstance(msg, str) and len(msg) > 5

    def test_query_sem_evidencias_retorna_contrato_ok(self):
        """Query que não encontra evidências ainda retorna contrato válido."""
        resp = self.client.post(
            "/query",
            json={"query": " tecnologia obscure xyz", "max_startups": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Contrato: deve ter startups (mesmo que 0) e briefing
        assert "startups" in body
        assert "briefing" in body

    def test_query_sem_max_startups(self):
        """Query sem max_startups usa o default."""
        resp = self.client.post("/query", json={"query": "ia"})
        assert resp.status_code == 200
        assert resp.json()["startups"] is not None


class TestQueryEdgeCases:
    """Testes de borda e fallback."""

    def setup_method(self):
        self.client = TestClient(get_app())

    def test_query_com_query_nao_encontrada(self):
        """Query que não encontra nada no repositório."""
        resp = self.client.post(
            "/query",
            json={"query": "techobscuro12345 lateral unknown"},
        )
        # O pipeline deve graceful fallback sem crashar
        assert resp.status_code == 200
        body = resp.json()
        assert "startups" in body
        assert "briefing" in body

    def test_query_blank_fields(self):
        """Query com fields em branco não quebra o pipeline."""
        resp = self.client.post(
            "/query",
            json={"query": "", "max_startups": 1},
        )
        # Deve retornar 422 ou fallback graceful (200 com briefing de "Sem startups")
        assert resp.status_code in (200, 422)


class TestQueryWithStartups:
    """Testes que efetivamente encontram startups com evidências (quando disponíveis)."""

    def setup_method(self):
        self.client = TestClient(get_app())

    def test_query_fintech_ia_acha_startups(self):
        """Query fintech+ia deve encontrar startups; briefing válido em ambos os modos."""
        resp = self.client.post(
            "/query",
            json={"query": "startup de fintech com inteligência artificial", "max_startups": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "startups" in body
        assert "briefing" in body
        nurture = body["briefing"].get("nurture_suggestion", "")
        if body["startups"]:
            # Com startups no KB, o briefing é real e NÃO deve conter fallback
            assert "Sem startups para nutrir" not in nurture
            assert "refinar a query" not in nurture
        else:
            # Sem startups (DB indisponível, sem KB local), briefing sugere próximos passos
            assert "refinar a query" in nurture or "revisar estratégia" in nurture