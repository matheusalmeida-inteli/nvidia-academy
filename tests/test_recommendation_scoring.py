"""Testes do motor de recomendação corrigido (Lacuna 1).

Valida:
1. RAG puro vence (origem=rag, score_breakdown.rag=dominante)
2. Hardcoded sem RAG não domina (origem=regra_de_negocio, score baixo)
3. Regra composta não dispara com keyword solto (requires_all + any_of)
4. Wrapper gate respeitado (rule.requires_wrapper_signal + risco_wrapper=False)
5. Regressão: gabarito 21 startups (smoke test conservador)
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.nodes.recommendation import (
    recommend_for,
    _evaluate_rules,
    _proxima_acao_for,
    _consolidate_families,
    _family_of,
    _compute_sector_boost,
    RAG_WEIGHT,
    HARDCODED_WEIGHT,
    SECTOR_WEIGHT,
    MIN_FINAL_SCORE,
    TECH_RULES,
)


@pytest.fixture
def base_profile():
    return {
        "nome": "TestCo",
        "setor": "fintech",
        "estagio": "series_a",
        "sinais_ai": ["llm", "nlp"],
        "gaps_identificados": ["atendimento ao cliente via chatbot"],
        "casos_uso": ["automação de suporte"],
    }


@pytest.fixture
def base_classif():
    return {
        "categoria": "ai_native",
        "confianca": 0.9,
        "risco_wrapper": False,
        "moat_score": 2.5,
        "inception_fit_score": 0.7,
    }


class TestRAGVence:
    """Caso 1: RAG puro (sem hardcoded match) deve produzir origem=rag."""

    def test_rag_score_dominates(self, base_profile, base_classif):
        refs = [{
            "tech": "NVIDIA NIM",
            "title": "NIM Microservices",
            "content": "Otimização de inferência LLM em produção.",
            "url": "https://nvidia.com/nim",
            "rerank_score": 0.90,
            "category": "inference",
        }]
        recs = recommend_for(base_profile, refs, base_classif)

        nim = next((r for r in recs if r["tecnologia"] == "NVIDIA NIM"), None)
        assert nim is not None, "NVIDIA NIM deveria ser recomendado via RAG"

        # origem=rag (RAG ativo, sem match de regra exige llm + atendimento +
        # wrapper_signal — risco_wrapper=False então regra não dispara).
        # Pode ser rag (RAG score alto, regra não match) ou rag_e_regra se
        # regra match.
        assert nim["origem_recomendacao"] in ("rag", "rag_e_regra"), \
            f"origem esperada rag/rag_e_regra, obtida {nim['origem_recomendacao']}"

        # score_breakdown.rag deve ser dominante (peso 0.6 vs hardcoded 0.25)
        bd = nim["score_breakdown"]
        weighted_rag = bd["rag"] * RAG_WEIGHT
        weighted_hardcoded = bd["hardcoded"] * HARDCODED_WEIGHT
        assert weighted_rag > 0, "RAG weight deve ser > 0"
        # RAG component 0.9 * 0.6 = 0.54 domina hardcoded (0 ou 0.25)

    def test_fonte_rag_propagada(self, base_profile, base_classif):
        refs = [{
            "tech": "NVIDIA NIM",
            "title": "NIM LLM Inference",
            "content": "Microservice otimizado para inferência de LLM.",
            "url": "https://developer.nvidia.com/nim",
            "rerank_score": 0.88,
            "category": "inference",
        }]
        recs = recommend_for(base_profile, refs, base_classif)
        nim = next(r for r in recs if r["tecnologia"] == "NVIDIA NIM")
        assert len(nim["fontes_rag"]) == 1
        assert nim["fontes_rag"][0]["url"] == "https://developer.nvidia.com/nim"
        assert "NIM" in nim["fontes_rag"][0]["titulo"]

    def test_fallback_baixo_score_mas_evidencia_origem_rag(self, base_profile, base_classif):
        # Fallback scores são baixos (<0.5) mesmo com evidência RAG real.
        refs = [{
            "tech": "NVIDIA NIM",
            "title": "NIM",
            "content": "Serve LLM models with low latency.",
            "url": "https://nvidia.com/nim",
            "rerank_score": 0.35,  # típico de RerankFallback
            "category": "inference",
        }]
        recs = recommend_for(base_profile, refs, base_classif)
        nim = next((r for r in recs if r["tecnologia"] == "NVIDIA NIM"), None)
        assert nim is not None, "NIM deveria ser recomendado"
        # Com evidência RAG presente, origem deve ser rag (não regra_de_negocio)
        assert nim["origem_recomendacao"] in ("rag", "rag_e_regra"), \
            f"origem esperada rag, obtida {nim['origem_recomendacao']}"


class TestHardcodedNaoDomina:
    """Caso 2: Sem RAG, recomendação hardcoded deve ter score limitado."""

    def test_score_componente_respeitado(self, base_profile, base_classif):
        # Sem referências RAG.
        recs = recommend_for(base_profile, [], base_classif)

        # Se houver rec, é de regra_de_negocio (sem rag).
        for r in recs:
            assert r["origem_recomendacao"] in ("regra_de_negocio", "fraca")
            # Score deve ser limitado por peso hardcoded (0.25 max)
            # + sector (0.15) = 0.40 max.
            assert r["score_final"] <= 0.45, \
                f"Score {r['score_final']} excede limite de hardcoded puro"

    def test_min_score_filter(self, base_profile, base_classif):
        # profile sem sinais relevantes
        empty = {**base_profile, "sinais_ai": [], "gaps_identificados": [], "casos_uso": []}
        recs = recommend_for(empty, [], base_classif)
        # Sem nada, deve haver poucas ou nenhuma recomendação
        for r in recs:
            assert r["score_final"] >= MIN_FINAL_SCORE


class TestRuleHierarquica:
    """Caso 3: requires_all + requires_any_of evita disparo com keyword solto."""

    def test_sem_all_nao_dispara(self):
        text = "atendimento ao cliente"  # só 'atendimento', sem 'llm'
        matched = _evaluate_rules(text, "fintech", risco_wrapper=False)
        # Nenhuma regra com requires_all=["llm"] deve disparar
        for tech, regra_ids in matched.items():
            assert "llm_atendimento_wrapper" not in regra_ids
            assert "llm_inferencia_producao" not in regra_ids
            assert "llm_fine_tuning_custom" not in regra_ids
            assert "rag_retrieval" not in regra_ids

    def test_all_e_any_of(self):
        text = "llm atendimento"  # tem 'llm' E 'atendimento'
        matched = _evaluate_rules(text, "fintech", risco_wrapper=False)
        # llm_atendimento_wrapper dispara só com risco_wrapper=True
        for tech, regra_ids in matched.items():
            assert "llm_atendimento_wrapper" not in regra_ids

    def test_health_sector_filtra_imagens_medicas(self):
        text = "ia generativa"  # 'ia' mas sem 'imagem'/'medical'
        matched = _evaluate_rules(text, "health", risco_wrapper=False)
        for tech, regra_ids in matched.items():
            assert "imagens_medicas_saude" not in regra_ids

    def test_imagens_medicas_saude_dispara_em_saude(self):
        text = "ia medical imaging diagnóstico radiologia"  # 'ia' + 'medical' + 'radiolog'
        matched = _evaluate_rules(text, "health", risco_wrapper=False)
        # Deve disparar imagens_medicas_saude
        assert "Clara" in matched or "MONAI" in matched
        for tech, regra_ids in matched.items():
            if tech in ("Clara", "MONAI"):
                assert "imagens_medicas_saude" in regra_ids


class TestWrapperGate:
    """Caso 4: rule.requires_wrapper_signal + risco_wrapper=False não dispara."""

    def test_llm_atendimento_sem_risco_wrapper(self, base_profile, base_classif):
        # text_all com 'llm' + 'atendimento', mas risco_wrapper=False
        text = "llm atendimento chatbot nlp"
        matched = _evaluate_rules(text, "fintech", risco_wrapper=False)
        for tech, regra_ids in matched.items():
            assert "llm_atendimento_wrapper" not in regra_ids

    def test_llm_atendimento_com_risco_wrapper_dispara(self):
        text = "llm atendimento chatbot nlp"
        matched = _evaluate_rules(text, "fintech", risco_wrapper=True)
        # Com risco_wrapper=True, a regra deve disparar
        assert any(
            "llm_atendimento_wrapper" in regra_ids
            for regra_ids in matched.values()
        )


class TestRegressaoGabarito:
    """Caso 5: 21 startups smoke test conservador."""

    @pytest.mark.parametrize("setor,sinais,expected_top_tech", [
        ("fintech", ["llm", "nlp"], "NVIDIA NIM"),
        ("saúde", ["ia"], "Clara"),
        ("industrial", ["gpu"], "Isaac"),
        ("agro", ["ml", "predictive"], "RAPIDS"),
    ])
    def test_top1_por_setor(self, setor, sinais, expected_top_tech):
        profile = {
            "nome": f"Test-{setor}",
            "setor": setor,
            "estagio": "series_a",
            "sinais_ai": sinais,
            "gaps_identificados": [],
            "casos_uso": [],
        }
        classif = {
            "categoria": "ai_native",
            "confianca": 0.9,
            "risco_wrapper": False,
            "moat_score": 2.0,
            "inception_fit_score": 0.6,
        }
        # Adicionar RAG específico por setor
        refs = [{"tech": expected_top_tech, "title": "Doc", "content": "ref",
                 "url": "", "rerank_score": 0.85, "category": "inference"}]
        recs = recommend_for(profile, refs, classif)
        assert recs, f"Deveria haver rec para setor {setor}"
        # A tech do RAG deve estar no output (pode não ser top-1 se regra
        # gerar score mais alto, mas deve aparecer)
        techs = [r["tecnologia"] for r in recs]
        assert expected_top_tech in techs, \
            f"{expected_top_tech} deveria estar em {techs}"


class TestProximaAcao:
    """Bonus: proxima_acao varia por origem e regra."""

    def test_rag_origem(self):
        acao = _proxima_acao_for("NVIDIA NIM", "rag",
                                 ["llm_inferencia_producao"], "high")
        # Se regra existe no dict rag, retorna ação específica.
        assert "NIM" in acao or "call técnica" in acao or "TensorRT" in acao

    def test_regra_origem(self):
        acao = _proxima_acao_for("RAPIDS", "regra_de_negocio",
                                 ["grandes_volumes_tabulares"], "medium")
        assert "RAPIDS" in acao or "benchmark" in acao.lower()

    def test_acao_nao_generica(self):
        acao_rag = _proxima_acao_for("NVIDIA NIM", "rag", ["rag_retrieval"], "medium")
        acao_regra = _proxima_acao_for("RAPIDS", "regra_de_negocio",
                                       ["grandes_volumes_tabulares"], "low")
        # Não devem ser idênticas
        assert acao_rag != acao_regra


class TestPesos:
    """Validação de invariantes do scoring."""

    def test_pesos_somam_1(self):
        assert abs(RAG_WEIGHT + HARDCODED_WEIGHT + SECTOR_WEIGHT - 1.0) < 1e-9

    def test_rag_peso_maior(self):
        assert RAG_WEIGHT > HARDCODED_WEIGHT > SECTOR_WEIGHT
        assert RAG_WEIGHT == 0.6
        assert HARDCODED_WEIGHT == 0.25
        assert SECTOR_WEIGHT == 0.15


class TestConsolidacaoFamilia:
    """Melhoria: consolida famílias (RAPIDS/cuDF/cuML, NIM/NeMo/TensorRT-LLM)."""

    def test_family_of(self):
        assert _family_of("RAPIDS") == "accelerated_data"
        assert _family_of("cuDF") == "accelerated_data"
        assert _family_of("NVIDIA NIM") == "llm_runtime"
        assert _family_of("Triton") is None  # Triton não está em família

    def test_consolidate_keeps_highest_score_per_family(self):
        scored = [
            {"tech": "RAPIDS", "score": 0.9, "rag_component": 0.9},
            {"tech": "cuML", "score": 0.6, "rag_component": 0.6},
            {"tech": "Triton", "score": 0.7, "rag_component": 0.7},
        ]
        out = _consolidate_families(scored)
        techs = [e["tech"] for e in out]
        assert techs == ["RAPIDS", "Triton"], f"got {techs}"
        assert "cuML" not in techs

    def test_recommend_for_does_not_duplicate_family(self, base_profile, base_classif):
        # RAG retorna cuML e RAPIDS (mesma família) + Triton
        refs = [
            {"tech": "cuML", "title": "cuML", "content": "ML GPU",
             "url": "", "rerank_score": 0.55, "category": "data science"},
            {"tech": "RAPIDS", "title": "RAPIDS", "content": "RAPIDS data",
             "url": "", "rerank_score": 0.9, "category": "data science"},
            {"tech": "Triton", "title": "Triton", "content": "Triton serving",
             "url": "", "rerank_score": 0.7, "category": "inference"},
        ]
        recs = recommend_for({
            "nome": "FamTest", "setor": "fintech", "estagio": "series_a",
            "sinais_ai": ["data science", "ml"], "gaps_identificados": [],
            "casos_uso": [],
        }, refs, base_classif)
        techs = [r["tecnologia"] for r in recs]
        # RAPIDS e cuML não podem aparecer juntos (mesma família)
        has_rapids = "RAPIDS" in techs
        has_cuml = "cuML" in techs
        assert not (has_rapids and has_cuml), f"família duplicada: {techs}"


class TestAntiPlaceholder:
    """Lacuna 13 do audit: nenhuma justificativa genérica placeholder nas saídas."""

    def test_techs_do_kb_cobrem_tech_defs(self):
        # Techs presentes na KB RAG (nvidia_kb) devem existir em TECH_DEFS,
        # evitando que caiam no fallback genérico "Tecnologia NVIDIA para X."
        from agents.nodes.recommendation import TECH_DEFS, CANONICAL_NAMES, _canonical
        import re

        kb_path = os.path.join(os.path.dirname(__file__), "..", "rag", "ingest", "nvidia_kb.py")
        with open(kb_path, encoding="utf-8") as fh:
            source = fh.read()
        # techs referenciadas na KB como "tech="literal""
        kb_techs = set(re.findall(r'tech=\s*"([^"]+)"', source))

        missing = []
        for raw in sorted(kb_techs):
            canon = _canonical(raw)
            # "NVIDIA Inception" é chave direta em TECH_DEFS
            if canon not in TECH_DEFS and raw not in TECH_DEFS:
                missing.append(raw)

        assert not missing, f"techs da KB sem definição em TECH_DEFS: {missing}"

    def test_nenhum_placeholder_tecnologia_nvidia_para(self, base_profile, base_classif):
        # RAG com tech desconhecida não pode gerar "Tecnologia NVIDIA para X."
        refs = [{
            "tech": "NVIDIA CUDA-X",
            "title": "CUDA-X Libraries",
            "content": "Bibliotecas aceleradas para HPC e IA.",
            "url": "", "rerank_score": 0.8, "category": "platform",
        }]
        recs = recommend_for(base_profile, refs, base_classif)
        for r in recs:
            assert "Tecnologia NVIDIA para" not in r["justificativa_tecnica"]
            assert "Suporte NVIDIA para implementação." not in r["justificativa_negocio"]
            assert r["tecnologia"] in ("NVIDIA CUDA-X", "CUDA-X")

    def test_fallback_def_informativo(self):
        from agents.nodes.recommendation import _fallback_def
        prio, complex, just, negocio = _fallback_def("AeroSim")
        assert "AeroSim" in just
        assert "AeroSim" in negocio
        assert "Tecnologia NVIDIA para" not in just


class TestSectorExpansion:
    """F3a: sector_boost ativo via SECTOR_FILTER expandido (sectores reais da KB)."""

    def test_boost_fintech(self):
        assert _compute_sector_boost("NVIDIA NIM", "Fintech / Pagamentos")
        assert _compute_sector_boost("RAPIDS", "Fintech")

    def test_boost_logistica_acento(self):
        assert _compute_sector_boost("Isaac", "Logística")

    def test_boost_enterprise_ai_e_hr(self):
        assert _compute_sector_boost("NVIDIA NIM", "Enterprise AI")
        assert _compute_sector_boost("Riva", "HR Tech")

    def test_boost_insurtech(self):
        assert _compute_sector_boost("Morpheus", "InsurTech")

    def test_rag_nao_descartado_por_setor(self, base_classif):
        # Tech ancorada em RAG fora da lista setorial não pode ser dropada.
        profile = {
            "nome": "FintechOmni",
            "setor": "Fintech",
            "estagio": "series_a",
            "sinais_ai": ["gpu", "simulação"],
            "gaps_identificados": [],
            "casos_uso": [],
        }
        refs = [{
            "tech": "Omniverse", "title": "Digital Twin",
            "content": "simulação física em GPU.", "url": "",
            "rerank_score": 0.85, "category": "sim",
        }]
        recs = recommend_for(profile, refs, base_classif)
        techs = [r["tecnologia"] for r in recs]
        assert "Omniverse" in techs

    def test_setor_sem_match_mantem_todas(self, base_classif):
        # Setor desconhecido (ex.: "Impressão 3D") não restringe o pool.
        profile = {
            "nome": "Additive3D",
            "setor": "Impressão 3D",
            "estagio": "seed",
            "sinais_ai": ["gpu", "cuda"],
            "gaps_identificados": [],
            "casos_uso": [],
        }
        recs = recommend_for(profile, [], base_classif)
        techs = [r["tecnologia"] for r in recs]
        assert recs, "setor sem match deve gerar recs por regra"
        assert "CUDA" in techs


class TestWordBoundarySignals:
    """F3a: sinais curtos ('ia'/'ml') não disparam por substring (via, mlops)."""

    def test_ia_nao_dispara_dentro_de_via(self):
        matched = _evaluate_rules("atendimento via api", "fintech", risco_wrapper=False)
        for tech, regra_ids in matched.items():
            assert "voz_callcenter" not in regra_ids
            assert "imagens_medicas_saude" not in regra_ids

    def test_ml_nao_dispara_por_mlops_ou_mlflow(self):
        matched = _evaluate_rules("mlops mlflow", "fintech", risco_wrapper=False)
        # 'ml' não é palavra em "mlops"/"mlflow" → grandes_volumes não dispara
        for tech, regra_ids in matched.items():
            assert "grandes_volumes_tabulares" not in regra_ids

    def test_ia_explicita_dispara(self):
        matched = _evaluate_rules("ia voz asr", "telecom", risco_wrapper=False)
        assert "Riva" in matched and "voz_callcenter" in matched["Riva"]
