# RAG da Base de Conhecimento NVIDIA

Este documento descreve a implementação do **RAG** (Retrieval-Augmented
Generation) do projeto: a base de conhecimento NVIDIA, o pipeline de ingestão,
o retrieval híbrido (dense + BM25), o reranking, a validação de citações e o
framework de avaliação. Satisfaz o requisito do **TAPI §5.3**.

## 1. Objetivo

O RAG permite ao sistema consultar conhecimento sobre tecnologias NVIDIA e
recuperar os trechos (chunks) mais relevantes para o perfil e os *gaps* de uma
startup. Essas referências alimentam o **Recommendation Agent**, que atribui
peso RAG na pontuação das recomendações.

## 2. Base de conhecimento (`rag/ingest/nvidia_kb.py`)

A base é definida em `NVIDIA_KB: list[NVIDIAChunk]` (dataclass com `id`,
`tech`, `category`, `title`, `content`, `url`, `tags`), cobrindo os itens do
TAPI §5.4:

- NVIDIA Inception, NVIDIA NIM, NeMo / NeMo Guardrails, Triton Inference
  Server, TensorRT-LLM, RAPIDS / cuDF / cuML, CUDA, Riva, Omniverse, Isaac,
  Clara / MONAI, Morpheus, AI Enterprise, AI Services e AI-Native Services.

**Dois modos de origem do conteúdo:**

1. **Real**: se `/tmp/nvidia_real_kb.json` existir (cache obtido por
   `fetch_real_kb`, conteúdo oficial NVIDIA), a KB é carregada **100% real**
   (`_load_real_kb` suprime a adição dos itens sintéticos definidos no
   módulo).
2. **Sintético**: na ausência do cache, a KB usa os chunks curados definidos
   diretamente no módulo (fonte primária: TAPI §8).

## 3. Chunking semântico (`rag/ingest/chunker.py`)

O `SemanticChunker` divide o texto em **sentenças** e agrupa em **chunks** de
tamanho alvo, refinando os limites por **distância semântica**:

1. **Segmentação por sentença**: regex `(?<=[.!?])\s+(?=[A-ZÁ-Ý])|\n`.
2. **Grouping por tamanho**: `target_size` (padrão 800 chars), `max_size`
   (1600), `overlap` (200).
3. **Breakpoints semânticos**: um ponto de corte é inserido onde a distância
   de cosseno entre vetores de sentenças consecutivas excede `semantic_threshold`
   (0.35), o que separa tópicos distintos.
4. **`RAG_SEMANTIC_CHUNKING=0`** desabilita o refinamento semântico e usa os
   chunks pai como estão.

O cache compartilhado `rag/ingest/shared.py` calcula os chunks uma vez por
processo (`get_chunked_texts()` / `get_chunked_meta()`), garantindo que o
ingestor e o retriever usem **exatamente o mesmo corpus**.

## 4. Embeddings (`rag/ingest/embeddings.py`)

Três provedores, em ordem de preferência:

### 4.1 CohereEmbedder (produção)
- **Com `COHERE_API_KEY`**: `embed-multilingual-v3.0` (1024 dims).
- `embed_async` para ingestão em lote; fallback automático para
  MultilingualEmbedder em caso de falha.

### 4.2 MultilingualEmbedder (default offline)
- `paraphrase-multilingual-MiniLM-L12-v2` (384 dims), suporte a 50+ idiomas
  incluindo português.
- Modelo carregado **uma vez por processo** (singleton) para evitar o custo de
  ~10s de carga a cada requisição.

### 4.3 LocalEmbedder (fallback extremo)
- TF-IDF + *n-grams* com hash (1536 dims), determinístico, sem custo e sem
  dependência de download. Utilizado se sentence-transformers não estiver
  disponível.

## 5. Ingestão no Qdrant (`rag/ingest/ingestor.py`)

`NVIDIAIngestor` realiza:
1. Cria/recria a collection `nvidia_knowledge` com **distância cosseno** e
   dimensão detectada dinamicamente por sonda (1024 Cohere / 384 multilingual /
   1536 local).
2. **Fitta o BM25** no corpus de chunks (`BM25.fit`).
3. Gera embeddings (Cohere ou local), monta `PointStruct` com payload
   (`parent_id`, `tech`, `category`, `title`, `content`, `url`, `tags`,
   `position`) e IDs UUID determinísticos (hash de parent + hash do texto), e
   faz `upsert`.

Execução:

```bash
pixi run python -m rag.ingest.ingestor
```

## 6. BM25 (`ingestor.BM25`)

Implementação leve e autocontida (sem dependência externa):

- Tokenização com stopwords PT/EN (`_STOPWORDS`).
- IDF com suavização `log((N - df + 0.5) / (df + 0.5)) + 1`.
- Formulação padrão de BM25 com `k1=1.5`, `b=0.75`.

**Cache em disco** (`rag/retrieval/bm25_cache.py`): o índice fittado é
serializado em `/tmp/rag_cache/bm25.pkl` **chaveado por hash do corpus**.
Se o corpus mudar, o hash invalida e o índice é refeito. Evita o refit a cada
inicialização do `HybridRetriever`.

## 7. Retrieval híbrido (`rag/retrieval/retriever.py`)

`HybridRetriever.retrieve(query, top_k_dense, top_k_sparse, top_k_rerank)`
executa as etapas (TAPI §5.3, itens 6–8):

### 7.1 Pré-processamento da query
1. **Query rewriting opcional** (`rewrite_query_with_llm`): ativa apenas com
   `RAG_QUERY_REWRITE=1` + LLM disponível. Converte a consulta natural em forma
   otimizada para retrieval.
2. **Query expansion** (`expand_query`): uma taxonomia PT/EN mapeia termos de
   domínio para variantes que aumentam recall (ex.: `fraud` →
   morpheus, rapids, cuml, anomaly, threat). A mesma query expandida é usada
   no embedding e no BM25.

### 7.2 Busca densa (Qdrant)
- Embed da query expandida (mesma fonte de embeddings da ingestão).
- `qdrant.query_points(collection, top_k_dense=20)`.
- Cada ponto vira dict com `score`, `tech`, `category`, `title`, `content`,
  `url`, `tags`, `source="dense"`.

### 7.3 Busca esparsa (BM25)
- Para cada chunk do corpus: `bm25.score(expanded, i)`.
- Top `top_k_sparse=20` com `source="bm25"`.

### 7.4 Category boost
`_apply_category_boost` aplica um **bônus aditivo** (`RAG_CATEGORY_BOOST=0.5`)
para chunks cuja categoria/tags/título compartilham termos de domínio com a
query (inference, serving, speech, robotics, health, etc.), limitado a 2 termos
para evitar que categoria ampla domine a relevância geral.

### 7.5 Deduplicação por parent
`_dedup_by_parent` mantém apenas o melhor chunk por `(tech, title)` dentro de
cada fonte, evitando que o mesmo documento apareça múltiplas vezes.

### 7.6 Fusão — Reciprocal Rank Fusion (RRF)
`_rrf` combina os ranqueamentos denso e esparso:

```
score(doc) = Σ dense_weight / (k + rank_dense + 1)
           + Σ sparse_weight / (k + rank_sparse + 1)
```

- `k` configurável (`RAG_RRF_K=55`), cap de documentos (`RAG_RRF_CAP=20`).
- Pesos por fonte: `RAG_RRF_DENSE_WEIGHT=1.0`, `RAG_RRF_SPARSE_WEIGHT=1.0`.
- Chaves são `tech::title` para evitar colisões entre fontes.

### 7.7 Reranking (`rag/retrieval/reranker.py`)

Interface `Reranker (Protocol)`: `async rerank(query, documents, top_k)`.

| Implementação      | Condição                     | Comportamento                                          |
|--------------------|------------------------------|--------------------------------------------------------|
| `CohereRerank`     | `COHERE_API_KEY` presente    | `rerank-multilingual-v3.0` (TAPI §5.3) via API         |
| `RerankFallback`   | sem API key / falha em runtime| Cosseno (0.7) + overlap de keywords (0.3), com cache de embeddings por texto |
| `MMRReranker`      | `RAG_MMR=1`                  | Envolve o reranker base; score = λ·relevância − (1−λ)·máx similaridade a selecionados (Jaccard) |

O `HybridRetriever` instancia o reranker em `__init__` com fallback automático
em runtime: se `CohereRerank.rerank` falhar, cai para `RerankFallback`.

`RAG_RERANK=0` desabilita o rerank (usado em avaliação A/B qualidade × custo).

### 7.8 Telemetria do rerank
O retriever registra `last_pre_rerank_scores`, `last_post_rerank_scores` e
`last_rerank_delta` (`reorder_fraction`, `kendall_tau`, `n_pool`, `n_returned`),
consumidos pelo nó `nvidia_rag` e persistidos na telemetria NDJSON.

### 7.9 Saída
Retorna os `top_k_rerank` documentos finais (após dedup por parent), cada um
com `rerank_score` e `rerank_source` (`cohere` / `local_fallback` / `none`).

## 8. Nó de agente RAG (`agents/nodes/nvidia_rag.py`)

### 8.1 Construção de queries (`build_rag_queries`)
A partir do perfil da startup, monta até 3 queries:
- Diretas com os gaps e casos de uso (primeiros 3 de cada);
- Específicas por sinais: LLM → `LLM inference production deployment
  optimization`, speech → `real-time speech AI`, visão computacional →
  `computer vision inference optimization`;
- Específicas por setor: fintech → fraude, saúde → imagem médica, agro → dados
  com GPU, indústria/IoT → manutenção preditiva;
- Fallback genérico → `AI startup optimization NVIDIA Inception`.

### 8.2 Execução
- Para cada perfil e cada query, `HybridRetriever.retrieve` com **retry até 3
  tentativas** (delays 0s/1s/2s).
- Dedupe por tecnologia mantendo o melhor score.
- **Validação de citações** (`validate_citations`): cada referência é aceita
  (`valid=True`) somente se o nome da tecnologia (ou alias canônico) aparecer
  no `content`/`title` do chunk (groundedness). Referências inválidas são
  descartadas (`invalid_refs`) e registradas em telemetria.
- Manter até **5 referências válidas** por startup (ordenadas por score).

### 8.3 Modo low-evidence
Se `state.low_evidence=True`, o nó não consulta o RAG e emite referências vazias
por startup, registrando `insufficient_evidence` nos `evidence_reasons`.

## 9. Avaliação (`rag/eval/`)

### 9.1 Golden set (`golden_set.py`)
33 queries categorizadas:
- `e001`–`e015`: cenários em inglês (TAPI §5.5);
- `p001`–`p012`: cenários em português com contexto brasileiro;
- `a001`–`a006`: queries ambíguas / multi-tecnologia.

Cada amostra tem `{id, query, techs_esperadas, contexto}`.

### 9.2 Métricas (`metrics.py`)
Métricas IR padrão sobre o top-k recuperado:
- `hit_rate@k`: % de queries com ≥1 tech esperada no top-k.
- `recall@k`: % médio de techs esperadas encontradas.
- `precision@k`: % de itens do top-k que são techs esperadas.
- `mrr`: recíproco da posição da primeira tech esperada.
- Match por substring case-insensitive (aceita "NVIDIA NIM" vs "NIM").

### 9.3 Scripts

| Script                     | Uso                                             |
|----------------------------|-------------------------------------------------|
| `python -m rag.eval.run_eval`    | Retrieval eval + breakdown de latência por estágio |
| `python -m rag.eval.run_eval --no-rerank` | A/B: qualidade com/sem rerank               |
| `python -m rag.eval.eval_e2e`    | RAG → citação → recomendação (groundedness + precision/recall de recomendação) |
| `python -m rag.eval.eval_local --retrieval --e2e` | Eval offline (sem Cohere/Qdrant)         |

`run_eval` grava relatório JSON com `--json out.json`, incluindo métricas
agregadas, latência média e p95, breakdown médio por estágio
(`expand_embed`, `dense`, `sparse`, `boost_dedup_rrf`, `rerank`) e efetividade
do rerank (reorder_fraction média, kendall_tau médio).

**Baseline observado (modo fallback local, sem API Cohere):**
`mrr ≈ 0.92`, `hit_rate@3 ≈ 1.0`, `hit_rate@1 ≈ 0.87`, `recall@3 ≈ 0.71`,
`latency_avg ≈ 9–10 ms` (ver `rag_e2e_full.json` e README).

## 10. Variáveis de configuração relevantes

| Variável                | Padrão      | Efeito                                        |
|-------------------------|-------------|-----------------------------------------------|
| `COHERE_API_KEY`        | (vazio)     | Habilita Cohere Embed + Rerank                |
| `COHERE_EMBED_MODEL`    | `embed-multilingual-v3.0` | Modelo de embedding            |
| `COHERE_RERANK_MODEL`   | `rerank-multilingual-v3.0` | Modelo de rerank            |
| `RAG_SEMANTIC_CHUNKING` | `1`         | `0` desabilita chunking semântico             |
| `RAG_CHUNK_TARGET/MAX/OVERLAP` | 800/1600/200 | Parâmetros do chunker               |
| `RAG_TOP_K_DENSE/SPARSE/RERANK` | 20/20/3 | Top-k por estágio                     |
| `RAG_RRF_K/CAP/DENSE_WEIGHT/SPARSE_WEIGHT` | 55/20/1.0/1.0 | RRF          |
| `RAG_CATEGORY_BOOST`    | `0.5`       | Bônus por categoria                             |
| `RAG_MMR`               | `0`         | `1` ativa MMR reranker (Λ=0.7)                |
| `RAG_QUERY_REWRITE`     | `0`         | `1` ativa reescrita de query via LLM           |
| `RAG_RERANK`            | `1`         | `0` desabilita rerank (A/B)                   |
| `RAG_CACHE_DIR`         | `/tmp/rag_cache` | Diretório do cache do BM25                |
| `QDRANT_HOST/PORT`      | localhost/6333 | Conector Qdrant                            |

Veja `docs/ENV.md` para a lista completa.