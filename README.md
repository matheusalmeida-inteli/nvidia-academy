# Academy — NVIDIA Startup AI Radar

Plataforma multi-agente para análise de startups brasileiras e recomendação de
tecnologias NVIDIA. Projeto do processo seletivo **Inteli Academy**.

> **Status:** sistema funcional. End-to-end pipeline (consulta → briefing) operacional.
> Suíte de testes: 110 passing (77 em `tests/` + 33 em `rag_audit/`). Eval RAG local: MRR ≈ 0.91, hit@3 ≈ 0.94.
> Veja a tabela de progresso no final deste README. Documentação detalhada em `docs/`.
>
> **Entrega:** 09/09 às 23:59h

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 16 + TypeScript + Tailwind)              │
│  └── UI dark com NVIDIA-green accents, briefing executivo    │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP/JSON
┌──────────────────▼──────────────────────────────────────────┐
│  API (FastAPI 0.141)                                        │
│  └── /health · /startups · /query                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  Multi-agent pipeline (LangGraph)                           │
│  Query Planner → Retriever → Extractor → Classifier →       │
│  Evidence Validator → NVIDIA RAG → Recommendation →         │
│  Briefing                                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  Dados                                                       │
│  ├── PostgreSQL 16   — startups + documentos textuais        │
│  ├── Qdrant          — embeddings (semantic chunking)       │
│  ├── BM25            — busca lexical sobre chunks            │
│  ├── Cohere Rerank   — reordenação cross-encoder            │
│  │                     (fallback local se sem API key)       │
│  └── Cohere Embed    — embed-multilingual-v3.0              │
│                        (fallback local se sem API key)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Estrutura

```
academy-nvidia-radar/
├── scraper/        # Coleta opcional (TAPI §7 lista de fontes)
├── docs/           # Documentação (arquitetura, RAG, agentes, banco, env, testes)
├── rag/
│   ├── ingest/
│   │   ├── nvidia_kb.py        # 23 chunks curados sobre NVIDIA techs
│   │   ├── chunker.py          # Semantic chunker (sentence + embedding distance)
│   │   ├── embeddings.py       # CohereEmbedder + LocalEmbedder fallback
│   │   ├── ingestor.py         # Ingestão Qdrant + BM25 fit
│   │   └── shared.py           # Cache compartilhado de chunks
│   ├── retrieval/
│   │   ├── retriever.py        # HybridRetriever (dense + BM25 + RRF + rerank)
│   │   ├── reranker.py         # CohereRerank + RerankFallback + MMRReranker
│   │   └── bm25_cache.py       # Cache em disco do índice BM25 (evita refit)
│   └── eval/                    # Avaliação de qualidade do RAG
│       ├── golden_set.py       # 33 queries (PT/EN, ambíguas, multi-tech)
│       ├── metrics.py          # MRR, hit_rate@k, recall@k, precision@k
│       ├── run_eval.py         # Retrieval eval + latency breakdown por stage
│       ├── eval_e2e.py         # Eval end-to-end RAG → citação → recomendação
│       └── eval_local.py       # Eval em modo offline (sem Cohere/Qdrant)
├── agents/         # 9 agentes LangGraph (hub supervisor + retry/replan)
│   ├── graph.py
│   ├── state.py
│   ├── llm.py
│   └── nodes/
│       ├── query_planner.py
│       ├── retriever.py
│       ├── extractor.py
│       ├── classifier.py
│       ├── evidence_validator.py
│       ├── supervisor.py      # hub central: retry/replan/briefing
│       ├── nvidia_rag.py
│       ├── recommendation.py
│       └── briefing.py
├── api/            # FastAPI bridge
├── web/            # Next.js 16 + TypeScript + Tailwind
├── tests/          # Testes de recomendação/scoring (tabela de regras)
├── rag_audit/      # Eval de regressão + melhorias do RAG
├── schema.sql
├── pixi.toml       # Pixi environment
└── .env.example
```

---

## Setup

### Pré-requisitos
- **PostgreSQL 16+** rodando em `localhost:5432`
- **Qdrant** rodando em `localhost:6333`
- Python 3.11+
- (Opcional) Node.js 20+ para o frontend

### 1. Iniciar infraestrutura
```bash
# PostgreSQL
/path/to/pixi/envs/default/bin/pg_ctl -D <data_dir> -l /tmp/pg.log start

# Qdrant (binário standalone — sem Docker)
QDRANT__STORAGE__STORAGE_PATH=./qdrant_storage /tmp/qdrant > /tmp/qdrant.log 2>&1 &
```

### 2. Criar schema
```bash
PGPASSWORD=nvidia_radar_pass psql -U nvidia_radar -h 127.0.0.1 -d nvidia_radar -f schema.sql
```

### 3. Instalar dependências
```bash
cp .env.example .env       # opcional: preencha COHERE_API_KEY para melhor qualidade
pixi install
```

### 4. Seed da base de startups
```bash
POSTGRES_HOST=127.0.0.1 pixi run python -m scraper.synthesize_docs
```
Carrega 56 startups curadas (14 ai_native, 40 ai_enabled, 2 non_ai) e gera 224 documentos sintéticos
(4 docs por startup). Atende ao requisito do TAPI §5.2 (30-80 startups, 3+ docs/empresa).

### 5. Ingestão da base NVIDIA (RAG)
```bash
pixi run python -m rag.ingest.ingestor
```
Lê `rag/ingest/nvidia_kb.py`, aplica semantic chunking, embed, BM25 fit e ingere no Qdrant.
Resultado típico: ~70 semantic chunks a partir de 23 entradas curadas.

### 6. Avaliação do RAG
```bash
# Retrieval eval (33 queries) + latency breakdown por stage
pixi run python -m rag.eval.run_eval --top-k 3 --json eval_report.json

# Eval end-to-end RAG → citation → recommendation
pixi run python -m rag.eval.eval_e2e --top-k 3 --json eval_e2e.json

# Modo local/offline (sem Cohere, sem Qdrant) — útil para CI
pixi run python -m rag.eval.eval_local --retrieval --e2e --json eval_local
```
O `run_eval` usa o golden set (33 queries), calcula MRR, hit_rate@k, recall@k,
precision@k, latência e um breakdown por estágio (expand_embed, dense, sparse,
rerank). O `eval_e2e` adiciona validação de citação (groundedness) e métricas
de recomendação (precision/recall) derivadas apenas de referências validadas.

Saída típica (modo fallback sem Cohere):
```
mrr                  0.922
hit_rate@3           1.000
hit_rate@1           0.867
recall@3             0.711
latency_avg_ms       9.5
```

### 7. Subir API + Frontend
```bash
# Terminal 1 — FastAPI
POSTGRES_HOST=127.0.0.1 QDRANT_HOST=localhost pixi run uvicorn api.main:app --port 8000

# Terminal 2 — Next.js
cd web && npm install && npm run dev
```

Acesse `http://localhost:3000` e rode uma consulta.

---

## Como funciona o RAG

**Pipeline de retrieval (TAPI §5.3):**

1. **Ingestão** — `rag/ingest/nvidia_kb.py` define 23 chunks curados sobre tecnologias NVIDIA.
2. **Limpeza/normalização** — texto já limpo (fonte primária = TAPI §8).
3. **Chunking semântico** — `rag/ingest/chunker.py`:
   - Split em sentenças (regex `(?<=[.!?])\s+(?=[A-ZÁ-Ý])`)
   - Grouping por tamanho (target 800 chars, max 1600, overlap 200)
   - Breakpoints semânticos (cosseno distance entre sentences > 0.35)
4. **Embeddings** — `rag/ingest/embeddings.py`:
   - **Com `COHERE_API_KEY`:** Cohere `embed-multilingual-v3.0`
   - **Sem API key:** local TF-IDF + hashed n-grams (offline, no cost)
5. **Armazenamento** — Qdrant collection `nvidia_knowledge` (cosine distance; dimensão
   detectada dinamicamente por sonda: 1024 Cohere / 384 multilingual / 1536 local)
6. **Query rewriting (opcional)** — LLM reescreve a query em forma otimizada
   para retrieval (`RAG_QUERY_REWRITE=1` + `OPENROUTER_API_KEY`).
7. **Query expansion** — taxonomia PT/EN adiciona termos de domínio (ex. "fraud" →
   morpheus, rapids, cuml) para melhorar recall.
8. **Busca híbrida** — `rag/retrieval/retriever.py`:
   - Dense: top-20 via Qdrant
   - Sparse: top-20 via BM25 (cacheado em disco via `bm25_cache.py`)
   - **Reciprocal Rank Fusion (RRF)** com k=55
   - Category boost + dedup por parent (tech+title)
9. **Reranking** — `rag/retrieval/reranker.py`:
   - **Com `COHERE_API_KEY`:** Cohere `rerank-multilingual-v3.0`
   - **Sem API key:** `RerankFallback` (cosseno + keyword overlap)
   - **`RAG_MMR=1`:** envolve o reranker com MMR para diversidade entre techs
   - Auto-fallback se Cohere falhar em runtime
10. **Validação de citação** — `agents/nodes/nvidia_rag.py` filtra referências
    cuja tech não aparece no conteúdo do chunk (groundedness), evitando sugerir
    tecnologia sem suporte no KB.
11. **Avaliação** — `rag/eval/run_eval.py` (retrieval + breakdown) e
    `rag/eval/eval_e2e.py` (RAG → citação → recomendação).

---

## Configuração (`.env`)

Veja `.env.example` para todas as variáveis. Principais:

| Variável | Padrão | Efeito |
|---|---|---|
| `COHERE_API_KEY` | (vazio) | Habilita Cohere Embed + Cohere Rerank. Vazio = fallback local. |
| `COHERE_EMBED_MODEL` | `embed-multilingual-v3.0` | Modelo de embedding. |
| `COHERE_RERANK_MODEL` | `rerank-multilingual-v3.0` | Modelo de rerank. |
| `RAG_SEMANTIC_CHUNKING` | `1` | `0` desabilita chunking (usa parent chunks). |
| `RAG_CHUNK_TARGET` | `800` | Tamanho alvo do chunk (chars). |
| `RAG_CHUNK_MAX` | `1600` | Tamanho máximo do chunk. |
| `RAG_CHUNK_OVERLAP` | `200` | Overlap entre chunks. |
| `RAG_TOP_K_DENSE` | `20` | Default do `retrieve()` — não é lido via env. |
| `RAG_TOP_K_SPARSE` | `20` | Default do `retrieve()` — não é lido via env. |
| `RAG_TOP_K_RERANK` | `3` | Default do `retrieve()` — não é lido via env. |
| `RAG_CACHE_DIR` | `/tmp/rag_cache` | Diretório do cache do BM25. |
| `RAG_QUERY_REWRITE` | `0` | `1` habilita reescrita de query via LLM (requer `OPENROUTER_API_KEY`). |
| `RAG_MMR` | `0` | `1` habilita MMR reranking (diversidade entre techs). |
| `RAG_MMR_LAMBDA` | `0.7` | Balanceamento relevância × diversidade do MMR. |
| `RAG_RRF_K` | `55` | Parâmetro k da Reciprocal Rank Fusion. |
| `RAG_RRF_CAP` | `20` | Nº máx. de docs retornados pela fusão. |
| `RAG_RRF_DENSE_WEIGHT` | `1.0` | Peso da fonte densa na fusão. |
| `RAG_RRF_SPARSE_WEIGHT` | `1.0` | Peso da fonte BM25 na fusão. |
| `RAG_CATEGORY_BOOST` | `0.5` | Bônus aditivo por match de categoria (soft boost). |
| `OPENROUTER_API_KEY` | (vazio) | Habilita LLM para agentes. Vazio = regras. |
| `POSTGRES_*` | ver `.env.example` | Conexão ao Postgres. |
| `QDRANT_*` | ver `.env.example` | Conexão ao Qdrant. |

---

## Endpoints da API

| Método | Path | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/startups?setor=&estagio=&search=&limit=&offset=` | Lista startups (filtros + contagem de docs) |
| POST | `/query` | Roda o pipeline multi-agente |
| POST | `/query/export` | Pipeline + download do briefing completo como JSON (print p/ PDF via Ctrl+P) |
| POST | `/candidates` | Cria candidato (upsert por `startup_id`) |
| GET | `/candidates?status=&categoria_ai=&assigned_to=` | Lista candidatos |
| GET | `/candidates/{id}` | Detalhe de um candidato |
| PATCH | `/candidates/{id}` | Atualiza candidato |
| DELETE | `/candidates/{id}` | Remove candidato |
| POST | `/candidates/{id}/nurture` | Registra ação de nurture |
| GET | `/candidates/{id}/nurture` | Histórico de nurture do candidato |
| GET | `/nurture/upcoming?days=` | Candidatos com próxima ação de nurture |

Exemplo `POST /query`:
```json
{
  "query": "AI-native startups de fintech usando LLMs",
  "max_startups": 5
}
```

Resposta: lista de startups com categoria, confiança, recomendações, briefing executivo.

---

## Como usar

Com API e frontend no ar (passo 7 do Setup), acesse `http://localhost:3000` e digite
uma consulta em linguagem natural. Alguns exemplos:

```
AI-native startups de fintech usando LLMs
Startups de healthtech com visão computacional
Empresas de cybersecurity que poderiam usar NVIDIA Morpheus
Quem está maduro para adotar NVIDIA Inception?
```

A mesma consulta pode ser feita direto na API:

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "AI-native startups de fintech usando LLMs", "max_startups": 5}'
```

O pipeline roda em ~2–3s por consulta (com LLM local/API) e devolve para cada startup:
classificação de maturidade/categoria, scores de Inception fit, evidências, moat e
recomendações de tecnologia NVIDIA. O painel de dados (`/candidates`, `/nurture/*`)
atende ao fluxo de CRM: atração → qualificação → nutrição.

> Fluxo completo de operação, observabilidade e avaliação: veja `docs/`.

---

## Diferencial

- **Pipeline multi-agente com 9 nós LangGraph** em hub-and-spoke (query planner →
  retriever → extractor → classifier → evidence validator → **supervisor** (decisor:
  retry/replan/degradacão graciosa) → NVIDIA RAG → recommendation → briefing),
  com telemetria NDJSON por etapa e fallback a regras quando não há LLM.
- **RAG híbrido iterado (12 melhorias)**: semantic chunking com breakpoints de cosseno,
  query expansion por taxonomia PT/EN, query rewriting via LLM, dense (Qdrant) + sparse
  (BM25 cacheado) + **Reciprocal Rank Fusion**, category boost, dedup por tech+title,
  rerank Cohere com fallback local determinístico e **MMR** para diversidade entre techs.
- **Validação de citação (groundedness)**: nenhuma tecnologia é recomendada sem aparecer
  no conteúdo do chunk recuperado — evita "alucinação" de referências.
- **Avaliação contínua**: golden set com 33 queries (PT/EN, ambíguas, multi-tech) e métricas
  MRR / hit_rate@k / recall@k / precision@k + breakdown de latência por estágio. No modo
  fallback local (sem Cohere): `mrr ≈ 0.92`, `hit_rate@3 ≈ 1.0`, `hit_rate@1 ≈ 0.87`,
  `recall@3 ≈ 0.71`, `latency_avg ≈ 9.5 ms`.
- **Resiliência offline**: funciona sem API key (embedding TF-IDF + hashing local) e até sem
  Qdrant (degrade para BM25 sobre `nvidia_kb.py`), permitindo eval em CI.
- **Base curada**: 56 startups reais, categorizadas, com 4 documentos textuais cada
  (desde o seed — atendendo ao TAPI §5.2).

---

## Cronograma

| Fase | Atividade | Status |
|------|-----------|--------|
| 0 | Scraping das 22 fontes do TAPI | ✅ (WOW, Latitud, Brazil Journal, NeoFeed, PEGN, Meio&Mensagem funcionais; + spiders cubo, open100, ace, abstartups, anjos, darwin customizados) |
| 1 | Curadoria + embeddings da base | ✅ (56 startups, 224 docs) |
| 2 | RAG NVIDIA + reranking | ✅ (Cohere Rerank + semantic chunking + eval) |
| 3 | 9 agentes LangGraph | ✅ (9 nós, supervisor hub com retry/replan/briefing, inclui `tests/test_supervisor.py`) |
| 4 | Interface Next.js | ✅ (dark theme, briefing panel) |
| 5 | Diferencial + polimento | ✅ (RAG iterado: 12 melhorias — chunking, query expansion, dedup, BM25 cache, latency breakdown, query rewriting, MMR, citation validation, eval e2e; briefing com relevância × fit e ações comerciais contextualizadas; TECH_DEFS completo sem justificativas placeholder; documentação em `docs/`) |

**Entrega**: 09/09 às 23:59h
