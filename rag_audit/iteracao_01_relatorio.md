# Iteração 1 — Auditoria Estrutural (Linha de Base)

## Metodologia
- Inspeção direta de código: `rag/ingest/`, `rag/retrieval/`, `rag/eval/`
- Execução do eval: `python -m rag.eval.run_eval --top-k 3`
- Verificação de componentes: Qdrant, BM25, Embedder, Reranker, KB
- Semântica: `retriever.py:37-38` (BM25 duplicado), `retriever.py:41` (Cohere key não lido de settings)

## Passo a passo do pipeline — Estado

### 1. Ingestão de documentos ✅ PARCIAL
- **Fundo**: `nvidia_kb.py` contém 43 `NVIDIAChunk` com conteúdo sintético (não real de páginas NVIDIA).
- **Problema**: conteúdo é gerado artificialmente com base no TAPI, não raspado de fontes reais (blogs, docs, whitepapers). Isso viola §5.3 ("blogs, documentações, vídeos transcritos, whitepapers e páginas oficiais").
- **Severidade**: Alta — a KB não contém conhecimento real, apenas paráfrases do TAPI.

### 2. Limpeza e normalização ✅
- `_SENTENCE_RE` em `chunker.py:22`: regex quebra sentenças em `.!?` + maiúscula. Funciona para PT/EN.

### 3. Chunking semântico ✅
- `SemanticChunker`: agrupa sentenças por tamanho (~400 chars) + breakpoints de distância semântica via embedding local.
- 122 chunks de 43 docs, tamanho médio 471 chars, min 151, max 821.
- **Problema**: o `_find_breakpoints` usa `LocalEmbedder` (TF-IDF hash-based) para calcular distância entre sentenças. Embedding local tem qualidade limitada — a "semantic distance" é baseada em n-gramas hasheados, não semântica real.
- **Severidade**: Média — funciona, mas o "semantic chunking" é decorativo (baseado em TF-IDF).

### 4. Geração de embeddings ✅ COM PROBLEMA
- `CohereEmbedder` tenta usar `embed-multilingual-v3.0` (API real) mas **sempre cai no fallback local** porque `HybridRetriever` não lê `get_settings().cohere_api_key`.
- O fallback `LocalEmbedder` usa TF-IDF hash-based com unigrams + bigrams. Vocabulário de ~10.000 tokens dos documentos de entrada.
- Qdrant recebe vectors 1536-dim (via fallback local quando não há API key).
- **Severidade**: Alta — embeddings de qualidade inferior estão em produção.

### 5. Armazenamento em vector database ✅
- Qdrant com 122 pontos, vetores de 1536 dimensões, distância COSINE.
- Bate com chunk cache (122 chunks). ✅

### 6. Busca híbrida ✅ COM PROBLEMA CRÍTICO
- RRF implementado em `retriever.py:123-142` com `k=60`.
- BM25 implementado com `k1=1.5, b=0.75` (padrão OK).
- **BUG CRÍTICO (retriever.py:37-38)**: `BM25` instanciado 2x na mesma linha.
- **BUG CRÍTICO (ingestor.py:57-59)**: IDF usa `.__rpow__(1)` que é `1**(expressão)` = **sempre 1.0**. IDF está totalmente quebrado — todos os tokens têm peso idêntico, o BM25 reduz a apenas TF (term frequency). **IDF corrigido com `math.log` na iteração 1.**

### 7. Reranking ✅ COM PROBLEMA CRÍTICO
- `CohereRerank` implementado com `rerank-multilingual-v3.0`.
- **BUG CRÍTICO**: `HybridRetriever.__init__` lia `os.environ.get("COHERE_API_KEY")` que NUNCA era setado, então sempre ativava `RerankFallback` (local). **Corrigido na iteração 1: agora lê de `get_settings().cohere_api_key`.**
- `RerankFallback` usa 0.7×cosine + 0.3×keyword_overlap — razoável para offline.

### 8. Geração de resposta com citações ✅ PARCIAL
- O `recommendation.py` propaga `fontes_rag` com título, URL, score e trecho do chunk.
- O `briefing.py` formata as citações no output final.
- **Problema**: não há etapa de "geração de resposta" via LLM no pipeline atual. O agente extrai perfis e classifica, mas a "resposta" é estrutural (dict de recomendações), não gerada por um LLM. As citações vêm dos chunks, não de uma resposta gerada.
- **Severidade**: Média — cumpre parcialmente o requisito de "citações" mas sem geração via LLM.

### 9. Avaliação de qualidade ✅
- `rag/eval/` com `golden_set.py` (15 samples), `metrics.py`, `run_eval.py`.
- Métricas: hit_rate@k, recall@k, precision@k, MRR, latência.

## Métricas de Baseline

| Métrica | Com RerankFallback | Com CohereRerank |
|---------|-------------------|------------------|
| MRR | 0.900 | 0.922 |
| hit_rate@1 | 0.800 | 0.867 |
| hit_rate@3 | 1.000 | 1.000 |
| recall@3 | 0.722 | 0.711 |
| precision@3 | 0.667 | 0.589 |
| latency_avg_ms | 11.3 | 1320.5 |

**Observação**: Cohere melhora MRR e hit_rate@1 mas reduz precision@3 e aumenta latência 117x.

## Bugs Corrigidos na Iteração 1

| Bug | Severidade | Correção |
|-----|-----------|----------|
| IDF sempre 1.0 (`.__rpow__(1)`) | Crítica | `math.log((n-freq+0.5)/(freq+0.5))+1` |
| BM25 duplicado (`self.bm25 = BM25()` ×2) | Baixa | Removida linha duplicada |
| Cohere nunca ativo (não lia settings) | Crítica | Adicionado fallback para `get_settings().cohere_api_key` |

## Achados em Aberto

1. **KB sintética**: conteúdo gerado de TAPI, não de fontes reais. Severidade: Alta.
2. **LocalEmbedder em produção**: embeddings TF-IDF em vez de Cohere embed-v3. Severidade: Alta (o embedder de chunks vai para Qdrant).
3. **Sem geração via LLM**: citações existem mas não há etapa de geração de resposta. Severidade: Média.
4. **Latência Cohere**: 11ms → 1320ms. Severidade: Média (trade-off已知, acceptable se API responde rápido).

## Re-verificação de achados anteriores
Primeira iteração — não há achados anteriores ainda. Esta seção será preenchida na Iteração 2.
