# Variáveis de Ambiente

Este documento lista todas as variáveis de ambiente lidas pelo sistema, seus
valores padrão, onde são usadas e o impacto de configurá-las.

O projeto **não carrega `.env` automaticamente na API** — as variáveis são
lidas via `os.environ`. O `.env.example` serve de referência e o
`scraper/config/settings.py` (Pydantic `BaseSettings` com `env_file=".env"`)
faz o carregamento automático para os módulos do `scraper/` e para quem
importa `get_settings()`.

> **Segurança:** nunca commite o `.env` real. Ele contém chaves de API. O
> `.env` atual contém uma `COHERE_API_KEY` ativa.

## 1. PostgreSQL — acesso à base estruturada

Lidas por `api/main.py` (módulo da API) e por `scraper/config/settings.py`.

| Variável           | Default             | Efeito                                             |
|--------------------|---------------------|----------------------------------------------------|
| `POSTGRES_HOST`    | `127.0.0.1` (API) / `localhost` (scraper) | Host do Postgres       |
| `POSTGRES_PORT`    | `5432`              | Porta do Postgres                                  |
| `POSTGRES_DB`      | `nvidia_radar`      | Nome do banco                                      |
| `POSTGRES_USER`    | `nvidia_radar`      | Usuário                                            |
| `POSTGRES_PASSWORD`| `nvidia_radar_pass` | Senha                                              |

> **Atenção à inconsistência:** a API lê `POSTGRES_HOST` com default
> `127.0.0.1`; o scraper (`settings.py`) usa `localhost`. Em máquinas com
> resolução diferente (ex.: IPv6), configure ambas explicitamente.

## 2. RAG — pipeline de retrieval

Lidas por `rag/ingest/shared.py`, `rag/retrieval/retriever.py`,
`rag/retrieval/reranker.py` e `rag/retrieval/bm25_cache.py`.

| Variável                     | Padrão        | Efeito                                                    |
|------------------------------|---------------|-----------------------------------------------------------|
| `RAG_SEMANTIC_CHUNKING`      | `1`           | `0` desabilita o chunking semântico (usa chunks pai)      |
| `RAG_CHUNK_TARGET`           | `800`         | Tamanho alvo do chunk (chars)                             |
| `RAG_CHUNK_MAX`              | `1600`        | Tamanho máximo do chunk                                   |
| `RAG_CHUNK_OVERLAP`          | `200`         | Sobreposição entre chunks                                 |
| `RAG_TOP_K_DENSE`            | `20`          | Top-k da busca densa (Qdrant)                             |
| `RAG_TOP_K_SPARSE`           | `20`          | Top-k da busca esparsa (BM25)                             |
| `RAG_TOP_K_RERANK`           | `3`           | Top-k final após rerank                                   |
| `RAG_RRF_K`                  | `55`          | Constante k da fusão RRF                                 |
| `RAG_RRF_CAP`                | `20`          | Limite de documentos na fusão                             |
| `RAG_RRF_DENSE_WEIGHT`       | `1.0`         | Peso da lista densa no RRF                                |
| `RAG_RRF_SPARSE_WEIGHT`      | `1.0`         | Peso da lista esparsa no RRF                              |
| `RAG_CATEGORY_BOOST`         | `0.5`         | Bônus aditivo por categoria afim                          |
| `RAG_RERANK`                 | `1`           | `0` desabilita o rerank (A/B quality × custo)             |
| `RAG_MMR`                    | `0`           | `1` ativa MMR (diversificação) no rerank                  |
| `RAG_MMR_LAMBDA`             | `0.7`         | Trade-off relevância × diversidade no MMR                |
| `RAG_QUERY_REWRITE`          | `0`           | `1` ativa reescrita de query via LLM (requer LLM)         |
| `RAG_CACHE_DIR`              | `/tmp/rag_cache` | Diretório do cache disco do BM25 (`bm25.pkl`)           |
| `RAG_TELEMETRY_DIR`          | `logs`        | Diretório dos arquivos NDJSON de telemetria (`agents/observability.py`) |

## 3. Cohere — embeddings + rerank (qualidade)

Lidas por `rag/ingest/embeddings.py` (via entrada) e
`rag/retrieval/reranker.py`.

| Variável               | Padrão                       | Efeito                                                 |
|------------------------|------------------------------|--------------------------------------------------------|
| `COHERE_API_KEY`       | vazio                        | Presença → usa Cohere Embed + Rerank; ausência → fallback local |
| `COHERE_EMBED_MODEL`   | `embed-multilingual-v3.0`    | Modelo de embeddings (1024 dims)                       |
| `COHERE_RERANK_MODEL`  | `rerank-multilingual-v3.0`   | Modelo de rerank (`settings.py` default diverge: `rerank-english-v3.0`) |

> O `.env` real usa `COHERE_RERANK_MODEL=rerank-multilingual-v3.0`. Ajuste no
> `scraper/config/settings.py` é `rerank-english-v3.0` — se você depende do
> `Settings` do scraper para RAG, defina a variável explicitamente.

**Modos de operação (sem custo):**
- Sem `COHERE_API_KEY`: embeddings `paraphrase-multilingual-MiniLM-L12-v2`
  (offline, 384 dims) e rerank `RerankFallback` (cosseno + overlap).
- Fallback extremo (sem sentence-transformers): `LocalEmbedder` TF-IDF +
  n-grams (1536 dims).

## 4. OpenRouter — LLM (opcional)

Lido por `agents/llm.py`.

| Variável               | Padrão                          | Efeito                                   |
|------------------------|---------------------------------|------------------------------------------|
| `OPENROUTER_API_KEY`   | vazio                           | Presença habilita chamadas LLM (planner, reescrita de query) |
| `OPENAI_API_KEY`       | vazio                           | Fallback secundário de credencial        |
| `LLM_MODEL`            | `anthropic/claude-3-haiku`      | Modelo usado nas chamadas LLM            |

Sem a chave, os agentes usam **heurísticas determinísticas** e o pipeline
completo funciona offline.

## 5. Qdrant — vetores da KB NVIDIA

Lido por `scraper/config/settings.py` (`qdrant_url`) e pelos conectores do
ingestor/retriever.

| Variável          | Default      | Efeito                       |
|-------------------|--------------|------------------------------|
| `QDRANT_HOST`     | `localhost`  | Host do Qdrant               |
| `QDRANT_PORT`     | `6333`       | Porta HTTP REST              |
| `QDRANT_GRPC_PORT`| `6334`       | Porta gRPC (se usada)        |

Collection criada pelo ingestor: `nvidia_knowledge` (distância cosseno).

## 6. Scraper (fora do escopo da entrega)

Lidas por `scraper/config/settings.py`. Usadas apenas se você executar o
scraper independentemente.

| Variável                   | Padrão                                             | Efeito                               |
|----------------------------|----------------------------------------------------|--------------------------------------|
| `SCRAPER_USER_AGENT`       | `Mozilla/5.0 ... Chrome/120.0 Safari/537.36`       | User-Agent HTTP                      |
| `SCRAPER_MIN_DELAY` / `SCRAPER_MAX_DELAY` | `1.0` / `3.0`                  | Delay mínimo/máximo entre requests   |
| `SCRAPER_TIMEOUT`          | `30`                                               | Timeout de requisição (s)            |
| `SCRAPER_MAX_CONCURRENCY`  | `4`                                                | Concorrência máxima do pool asyncpg  |
| `SCRAPER_RESPECT_ROBOTS`   | `true`                                             | Respeita robots.txt                  |
| `LOG_LEVEL`               | `INFO`                                             | Nível de log                         |
| `DATA_DIR`                | `./data`                                           | Diretório raw/processed/exports      |

## 7. Exemplo minimizado de `.env`

```dotenv
# Dados
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=nvidia_radar
POSTGRES_USER=nvidia_radar
POSTGRES_PASSWORD=nvidia_radar_pass

# RAG
RAG_SEMANTIC_CHUNKING=1
RAG_TOP_K_DENSE=20
RAG_TOP_K_SPARSE=20
RAG_TOP_K_RERANK=3

# Qualidade (opcional — sem chave o sistema roda em modo fallback local)
COHERE_API_KEY=
COHERE_RERANK_MODEL=rerank-multilingual-v3.0
OPENROUTER_API_KEY=
```

## 8. Variáveis de frente-web / Docker

- `web/.env.local` (Next.js): `NEXT_PUBLIC_API_URL` aponta para a API
  (padrão `http://localhost:8000`).
- `docker-compose.yml` define `POSTGRES_USER/PASSWORD/DB` para o serviço
  `postgres` e porta 6333 para `qdrant`; o serviço `cohere-rerank` é um
  container GPU (fora do código Python).