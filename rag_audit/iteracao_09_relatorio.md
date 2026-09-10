# Iteração 9 — Tuning de Retrieval + Pipeline de Recomendação

## Metodologia
1. Auditar parâmetros de tuning do RAG (RRF k, pesos dense/sparse, category boost)
2. Aplicar tuning e validar com testes unitários + eval
3. Auditar o motor de recomendação e corrigir gargalos de precisão/relevância

---

## Tuning de Retrieval

### RRF — chave de dedup corrigida
- **Antes**: `_rrf` usava só `title` como chave → chunks de techs diferentes com o
  mesmo título colidiam em um único bucket, perdendo resultados.
- **Depois**: chave `(tech ::: title)` impede fusão incorreta.
- RRF agora é configurável via env: `RAG_RRF_K` (default 55), `RAG_RRF_CAP` (20),
  `RAG_RRF_DENSE_WEIGHT` / `RAG_RRF_SPARSE_WEIGHT` (default 1.0).

### Category boost — de hard para soft
- **Antes**: match de categoria reordenava por 0/1 ANTES do score → empurrava um
  chunk irrelevante de domínio amplo para o topo, ignorando relevância.
- **Depois**: bônus aditivo (`RAG_CATEGORY_BOOST`, default 0.5) aplicado ao score —
  relevância continua dominando; categoria é sinal secundário.

### Medição (modo local/offline — BM25 + RerankFallback; sem Qdrant/Cohere)

| Config | MRR | hit_rate@1 | recall@3 | precision@3 |
|--------|-----|-----------|----------|-------------|
| **Sem MMR** (default) | **0.889** | 0.818 | **0.672** | **0.722** |
| `RAG_MMR=1` | 0.894 | 0.818 | 0.652 | 0.687 |

**Insight**: em modo fallback, MMR melhora levemente MRR mas degrada recall@3 e
precision@3 (força diversidade e desloca techs corretas do top-3). Confirma que
MMR deve ser opt-in (já é, default `0`).

**Eval e2e (local)**: retrieval_hit@k 0.627 · citation_validity 1.000 ·
recommendation_precision 0.732 · recommendation_recall 0.672 — sem regressão
após o tuning (os benefícios do RRF-key-fix só se manifestam com dense ativo).

---

## Pipeline de Recomendação

### Consolidação de famílias de techs
- Novas `TECH_FAMILIES`: `accelerated_data` (RAPIDS/cuDF/cuML) e
  `llm_runtime` (NIM/NeMo/TensorRT-LLM).
- `_consolidate_families` mantém apenas o membro de maior score de cada família —
  reduz ruído de recs redundantes cobrindo o mesmo caso de uso.

### Origem correta quando score fallback é baixo
- **Antes**: origem dependia de `rag_component >= 0.5`. Em fallback, scores são
  `cosine+keyword < 0.5`, então rec com evidência RAG real era rotulada
  `regra_de_negocio` (e prefixada com "[Sem evidência RAG...]").
- **Depois**: presença de evidência RAG (chunk com conteúdo citando a tech) também
  conta para `origem=rag`. Rotulagem fiel mesmo em modo fallback.

---

## Testes
- `rag_audit/test_regression.py::TestRRFkParameter` — 3 testes (k default, pesos, key por tech+title).
- `rag_audit/test_rag_improvements.py::TestRAGtuning` — soft boost não sobrepõe relevância.
- `tests/test_recommendation_scoring.py::TestConsolidacaoFamilia` — famílias não duplicam.
- `tests/...::TestRAGVence.test_fallback_baixo_score_mas_evidencia_origem_rag` — origem fiel no fallback.

**Suíte completa: 55 passed.**

## Novos recursos/arquivos
- `rag/eval/eval_local.py` — rodar evals em modo offline (CI / sem chaves).

## Flags novas
`RAG_RRF_K` · `RAG_RRF_CAP` · `RAG_RRF_DENSE_WEIGHT` · `RAG_RRF_SPARSE_WEIGHT` · `RAG_CATEGORY_BOOST`

## Bugs em Aberto
| # | Bug | Severidade | Ação |
|---|------|------------|------|
| I2-3 | Rate limit Cohere (trial 10/min) | Crítica | Produzir chave (qualidade cai de hit@3 97% → 0.627 local) |
| I8-2 | LocalEmbedder não multilíngue | Alta | Cohere embed em produção |
