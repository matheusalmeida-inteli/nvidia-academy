# Testes do Projeto

Este documento descreve as suítes de teste, como executá-las e a cobertura de
cada uma. Estado atual (verificado nesta revisão): **110 testes passando
(77 em `tests/` + 33 em `rag_audit/`, sendo 16 do run `test-rag`)**.

## 1. Como executar

O ambiente é gerenciado por **Pixi** (`pixi.toml`, pytest ≥9.1). A partir da
raiz do projeto:

```bash
# Todas as suítes
pixi run pytest -q

# Suíte específica
pixi run pytest tests/ -q
pixi run pytest rag_audit/test_regression.py -v
pixi run pytest rag_audit/test_rag_improvements.py -v

# Executável direto (sem pixi), mesmo resultado
./.pixi/envs/default/bin/python -m pytest -q
```

> **Aviso:** os testes de `rag_audit` importam módulos que definem as variáveis
> de ambiente de conexão (Postgres) com valores padrão no próprio arquivo; a
> maior parte não exige o banco, apenas o corpus de chunks (que é calculado
> em cache em `rag/ingest/shared.py`). Os testes de retriever toleram Qdrant
> indisponível (fallback BM25).

## 2. Suíte 1 — Motor de recomendação (`tests/test_recommendation_scoring.py`)

Unit tests do scoring corrigido do Recommendation Agent (26 testes). Cobrem as
regressões da Lacuna 1:

| Classe de teste            | O que valida                                                        |
|----------------------------|---------------------------------------------------------------------|
| `TestRAGVence`             | RAG puro domina o score (origem `rag`/`rag_e_regra`), propagação de `fontes_rag`, fallback com score baixo mas evidência real mantém origem `rag` |
| `TestHardcodedNaoDomina`   | Sem RAG, regras não dominam (score ≤ 0.45); filtro por `MIN_FINAL_SCORE` |
| `TestRuleHierarquica`      | `requires_all` + `requires_any_of` impedem disparo com keyword solto; setor não dispara regra médica fora de saúde |
| `TestWrapperGate`          | Regra com `requires_wrapper_signal` só dispara com `risco_wrapper=True` |
| `TestRegressaoGabarito`    | Smoke por setor (fintech→NIM, saúde→Clara, industrial→Isaac, agro→RAPIDS) |
| `TestProximaAcao`          | `proxima_acao` varia por origem/regra e não é genérica               |
| `TestPesos`                | Invariantes: pesos somam 1; `RAG(0.6) > HARDCODED(0.25) > SECTOR(0.15)` |
| `TestConsolidacaoFamilia`  | Famílias `accelerated_data` e `llm_runtime` não duplicam techs       |
| `TestAntiPlaceholder`      | Techs da KB cobertas por `TECH_DEFS`; sem justificativa genérica; `_fallback_def` informativo |

## 2b. Suítes de integração e utilitários (`tests/`)

- `tests/test_graph_integration.py` (4 testes) — fluxo nominal, replan limitado,
  back-edges do supervisor e compilação do grafo; roda sem Qdrant/DB (refs
  determinísticas no `nvidia_rag` stub).
- `tests/test_supervisor.py` (12 testes) — decisões do supervisor hub.
- `tests/test_spiders.py` (6 testes) — spiders de alta prioridade (cubo, open100,
  ace, abstartups, anjos, darwin) com HTML de exemplo offline.
- `tests/test_retriever.py` (3 testes) — SQL de busca e ordenação por relevância
  (peso por campo: nome 3.0 > setor 2.0 > descricao 1.0).
- `tests/test_api_validation.py` (7 testes) — validação do `QueryRequest`
  (query em branco → erro; `max_startups` em faixa; strip) e pesos de evidência
  por tipo de documento.

## 3. Suíte 2 — Regressão do RAG (`rag_audit/test_regression.py`)

Fixações críticas das iterações 1–10 (17 testes):

| Classe | O que valida |
|--------|--------------|
| `TestBM25IDFCorrection` | Stopwords PT/EN; fórmula `log` do IDF; ausência de classe BM25 duplicada no retriever |
| `TestCohereRerankConfig` | Retriever lê a API key via `get_settings()` |
| `TestRRFkParameter` | k=55; pesos por fonte afetam o ranking; chave de fusão = `tech::title` (sem colidir techs com mesmo título) |
| `TestCoverageNicheTechs` | Morpheus top-1 em cybersec; Isaac top-1 em robótica |
| `TestGracefulDegradation` | Qdrant fora do ar → retriever segue via BM25 |
| `TestDeterminism` | Mesma query → mesmos resultados |
| `TestCitationFidelity` | Chunks citam tecnologias NVIDIA (>80% de cobertura) |
| `TestMultilingualEmbedder` | Embedder PT/EN mantém similaridade semântica; 384 dims |
| `TestNoDataLeakage` | Sem chunks tautológicos/derivados das queries de teste |

## 4. Suíte 3 — Melhorias do RAG (`rag_audit/test_rag_improvements.py`)

As **12 melhorias** da iteração 9 (16 testes):

| Classe | O que valida |
|--------|--------------|
| `TestChunkingDefaults` | `target=800 / max=1600 / overlap=200` e defaults conduzidos por env |
| `TestQueryExpansion` | Expansão adiciona termos de domínio e preserva a query sem match |
| `TestDedupByParent` | Mantém o melhor chunk por `tech::title` |
| `TestMMRReranker` | MMR respeita `top_k` e diversifica |
| `TestBm25Cache` | Round-trip do cache preserva scores; invalidação por hash do corpus |
| `TestCitationValidation` | `validate_citations` aprova tech presente e reprova sem groundedness; alias (TensorRT-LLM) valida |
| `TestLatencyInstrumentation` | `last_stage_times` popula `expand_embed/dense/sparse/rerank` |
| `TestEvalHelpers` | `_normalize` e `_matches` do `eval_e2e` |
| `TestGoldenSetExpanded` | Golden set ≥30 amostras com PT e ambíguas |
| `TestRAGtuning` | Category boost aditivo não sobrescreve relevância; `_cat_bonus` registrado sem vazamento de mutação |

## 5. Validações complementares (scripts e evals)

Não são testes unitários, mas compõem a checagem de qualidade:

| Ferramenta                                  | Uso                                                  |
|---------------------------------------------|------------------------------------------------------|
| `python -m rag.eval.run_eval`               | Retrieval eval (33 queries, MRR/hit_rate@k/recall@k/precision@k/latência) |
| `python -m rag.eval.eval_e2e`               | RAG → citação → recomendação (groundedness, precision/recall) |
| `python -m rag.eval.eval_local`             | Eval offline (sem Cohere/Qdrant) — útil em CI        |
| `python scripts/audit_harness.py`           | Harness E2E: dispara `/query` com cenários do TAPI e grava execuções em `/tmp/audit_runs.jsonl` |

> Métricas de referência (modo fallback, sem Cohere): `mrr ≈ 0.92`,
> `hit_rate@3 ≈ 1.00`, `hit_rate@1 ≈ 0.87`, `recall@3 ≈ 0.71`,
> `latency_avg ≈ 9.5 ms`. Histórico das iterações em `rag_audit/relatorio_*.md`
> e `scripts/audit_iter*.md`.

## 6. Resultado atual

```
$ ./.pixi/envs/default/bin/python -m pytest tests/ rag_audit/ -q
91 passed, 6 warnings in ~37s
```

Distribuição: motor de recomendação (26) + integração/supervisor (16) + spiders
(6) + retriever/API validation (10) + `rag_audit` (33 = 16 melhorias + 17 regressão).
Os warnings são de bibliotecas de terceiros (qdrant-client, cohere, pydantic)
e não afetam a corretude.

## 7. Como estender

- Adicione unit tests em `tests/` quando alterar motores de decisão puros
  (ex.: `recommendation.py`, `classifier.py`) — essas funções não dependem de
  infra e rodam em CI sem banco.
- Para mudanças no RAG, adicione casos em `rag_audit/` seguindo o padrão das
  classes existentes (imports diretos das funções; evite chamadas de rede).
- Para novos cenários de avaliação, amplie `rag/eval/golden_set.py` e rode
  `run_eval`/`eval_e2e`.