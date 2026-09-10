# Módulo `rag/` — Retrieval-Augmented Generation (RAG)

Pilha RAG híbrida sobre a base de conhecimento NVIDIA. Responsável por
preparar a base, recuperar os trechos mais relevantes para uma consulta e
medir a qualidade do pipeline.

Visão geral detalhada: [`docs/RAG.md`](../docs/RAG.md).

## Submódulos

| Submódulo | Responsabilidade |
|---|---|
| `rag/ingest/` | Curadoria da KB NVIDIA, chunking semântico, embeddings e ingestão no Qdrant + fit do BM25 |
| `rag/retrieval/` | Busca híbrida (dense Qdrant + sparse BM25), fusão RRF e reranking |
| `rag/eval/` | Avaliação de qualidade contra o golden set (33 queries) |

## `rag/ingest/`

| Arquivo | Papel |
|---|---|
| `nvidia_kb.py` | Base de conhecimento curada (23 entradas por tecnologia) + carregador da KB real em `/tmp/nvidia_real_kb.json` |
| `chunker.py` | Segmentação semântica (split por sentença + breakpoints por distância de cosseno) |
| `embeddings.py` | CohereEmbedder (API), LocalEmbedder (384-d multilingual) e fallback TF-IDF hashing (1536-d) |
| `ingestor.py` | Classe `NVIDIAIngestor`: cria collection, embed, upsert no Qdrant e fit do BM25 |
| `shared.py` | Cache compartilhado dos chunks (ingestor e retriever usam a mesma base) |
| `fetch_real_kb.py` | Baixa documentação real da NVIDIA para uso em modo "real only" |

Uso:

```bash
pixi run python -m rag.ingest.ingestor
```

## `rag/retrieval/`

| Arquivo | Papel |
|---|---|
| `retriever.py` | `HybridRetriever`: expande a query, busca dense + sparse, aplica RRF, dedup e rerank |
| `reranker.py` | `CohereRerank`, `RerankFallback` (cosseno + keyword) e `MMRReranker` (diversidade) |
| `bm25_cache.py` | Índice BM25 persistido em disco (cache por hash do corpus, evita refit) |

O `HybridRetriever` é usado pelo nó `nvidia_rag` dos agentes e pela avaliação.

## `rag/eval/`

| Arquivo | Papel |
|---|---|
| `golden_set.py` | Golden set com 33 queries (PT/EN, ambíguas, multi-tech) e techs esperadas |
| `metrics.py` | MRR, hit_rate@k, recall@k, precision@k |
| `run_eval.py` | Eval de retrieval + breakdown de latência por estágio |
| `eval_e2e.py` | Eval ponta a ponta: retrieval → validação de citação → recomendação |
| `eval_local.py` | Mesmas evals em modo offline (sem Cohere/Qdrant) — útil para CI |

Uso:

```bash
pixi run python -m rag.eval.run_eval --top-k 3 --json /tmp/eval.json
pixi run python -m rag.eval.eval_e2e --top-k 3 --json /tmp/eval_e2e.json
pixi run python -m rag.eval.eval_local --retrieval --e2e --json /tmp/eval_local
```

## Fluxo resumido

1. `ingest` gera os chunks semânticos (cache em `shared.py`) e o índice BM25.
2. `retriever` recupera top-20 dense + top-20 sparse, funde por RRF e reranka (Cohere ou local).
3. `eval` valida a qualidade com métricas de IR e groundedness.

Configuração (variáveis `RAG_*`): ver [`docs/ENV.md`](../docs/ENV.md).## RAG Evaluation Baseline (rag_audit/eval_final.json)
- MRR: 0.889 | hit_rate@1: 0.8 | hit_rate@3: 1.0 | recall@3: 0.722 | precision@3: 0.756
- Latency avg: 2644ms | p95: 11229ms | samples: 15 | top_k: 3 | rerank: CohereRerank
- Golden queries: 33 (15 EN + 12 PT + 6 ambiguous). Metrics: MRR, hit_rate@k, recall@k, precision@k.
