# NVIDIA Startup AI Radar — Visão Geral do Projeto

## 1. Contexto

Este projeto é a entrega do **Processo Seletivo Inteli Academy**, implementando o
TAPI (Termo de Abertura do Projeto) **"NVIDIA Startup AI Radar"**. O objetivo é
construir uma plataforma multi-agente capaz de analisar startups brasileiras a
partir de uma base de dados pré-populada, diagnosticar sua maturidade técnica
em IA e recomendar tecnologias NVIDIA adequadas ao perfil de cada empresa.

A solução é uma ferramenta de inteligência para apoiar o **Gerente de Startups
& VCs da NVIDIA no Brasil** a atrair, qualificar e nutrir startups para o
programa **NVIDIA Inception**.

### 1.1 Problema de negócio (TAPI §1)

Grandes laboratórios de IA (OpenAI, Anthropic, Google DeepMind, Meta) deixaram
de atuar apenas como fornecedores de modelos fundacionais e subiram na cadeia
de valor, oferecendo APIs, agentes, ferramentas e produtos finais. Isso cria
uma ameaça direta a startups que se posicionam apenas como *wrappers* de LLMs,
mas abre uma oportunidade para startups que se tornam **AI-native services**
(combinação de software, agentes, dados proprietários, automação e serviço
especializado).

A NVIDIA tem posição estratégica: muitas startups usam IA em APIs externas,
mas não otimizam a stack técnica. A plataforma identifica esses *gaps* e
recomenda tecnologias NVIDIA (NIM, NeMo, Triton, RAPIDS, etc.).

### 1.2 Pergunta norteadora (TAPI §3)

> Como a NVIDIA pode identificar, atrair e nutrir startups brasileiras
> AI-native em um contexto no qual os grandes labs de IA estão ameaçando
> startups que dependem apenas de wrappers de LLM?

## 2. Objetivos do sistema (TAPI §2)

1. Consultar e filtrar, a partir de uma base pré-populada, startups brasileiras
   com sinais de uso intensivo de IA.
2. Estruturar e interpretar as informações públicas dessas empresas.
3. Avaliar possíveis *gaps* na stack de IA da empresa.
4. Consultar uma base de conhecimento sobre tecnologias NVIDIA.
5. Recomendar as tecnologias NVIDIA mais adequadas para a startup analisada.
6. Gerar um *briefing* executivo para apoiar a abordagem comercial, técnica e
   comunitária pelo NVIDIA Inception.

## 3. Escopo (TAPI §4)

**Dentro do escopo:**

- Pipeline multi-agente orquestrada com **LangGraph**.
- Recuperação de empresas relevantes da base pré-populada.
- Estruturação de texto não estruturado em perfil estruturado.
- Classificação de maturidade AI-native (3 categorias).
- Validação de evidências com rastreabilidade via `url_fonte`.
- **RAG** sobre uma base de conhecimento NVIDIA com **reranking**.
- Motor de recomendação personalizado.
- *Briefing* executivo com 3 ângulos (comercial, técnico, comunitário).
- Interface web.

**Fora do escopo:**

- Construção de crawlers, scrapers ou pipeline de coleta automatizada de dados
  na web. A base de startups é fornecida pré-populada (via seed manual).
  Enriquecimento por fontes externas é opcional.
  (O repositório contém um módulo `scraper/` como recurso opcional não
  utilizado na entrega final.)

## 4. Arquitetura em alto nível

```
┌──────────────────────────────────────────────────────────────┐
│  Web (Next.js 16 + TypeScript + Tailwind)                     │
│  ├── Consulta de startups, briefing executivo, nurture        │
│  └── HTTP/JSON (fetch com timeout de 90s)                    │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  API (FastAPI) — api/main.py                                  │
│  ├── GET  /health                                             │
│  ├── GET  /startups                                           │
│  ├── POST /query          → orquestra o pipeline multi-agente │
│  ├── POST/GET/PATCH/DELETE /candidates  (CRM/nurture)         │
│  └── POST/GET /nurture, /candidates/{id}/nurture              │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  Pipeline multi-agente (LangGraph) — agents/graph.py           │
│  query_planner → retriever → extractor → classifier →          │
│  evidence_validator → supervisor (hub: replan/retry/briefing)│
│  → nvidia_rag → recommendation → briefing → END               │
└──────────────────────────────┬───────────────────────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
┌───────────────────┐  ┌───────────────┐  ┌─────────────────┐
│ PostgreSQL 16      │  │ Qdrant        │  │ Cohere / local  │
│ startups/documents │  │ nvidia_knowledge│ │ embed + rerank  │
│ candidates/nurture │  │ (dense search)│  │ (RAG)           │
└───────────────────┘  └───────┬───────┘  └─────────────────┘
                               │ BM25 (cache em disco) → RRF
                               ▼
                    HybridRetriever (rag/retrieval/retriever.py)
```

## 5. Stack tecnológica

| Camada          | Tecnologia                                       | Papel                                          |
|-----------------|--------------------------------------------------|------------------------------------------------|
| Orquestração    | LangGraph (≥0.2)                                 | Grafo de estado multi-agente                   |
| API             | FastAPI (0.141) + Uvicorn                        | Bridge HTTP para o pipeline e CRM              |
| Dados          | PostgreSQL 16 (asyncpg)                          | Dados estruturados de startups, documentos, CRM|
| Vetores         | Qdrant (collection `nvidia_knowledge`)           | Busca densa sobre chunks da base NVIDIA        |
| Lexical         | BM25 (implementação própria em `ingestor.BM25`)  | Busca esparsa sobre o mesmo corpus             |
| Embeddings      | Cohere `embed-multilingual-v3.0` (fallback: `paraphrase-multilingual-MiniLM-L12-v2`, LocalEmbedder) | Vetores de semântica                          |
| Reranking       | Cohere `rerank-multilingual-v3.0` (fallback local cosseno + overlap) | Reordenação pós-fusão                          |
| LLM (opcional)  | OpenRouter (padrão `anthropic/claude-3-haiku`)   | Plano de query e reescrita de consulta, uso em nós com LLM |
| Frontend        | Next.js 16, React 19, TypeScript, Tailwind CSS   | Dashboard                                  |
| Ambiente        | Pixi (Python 3.11)                               | Gerenciamento de dependências e executáveis    |

O sistema é **híbrido no uso de IA**: todos os agentes possuem implementação
rule-based de fallback e funcionam **sem nenhuma API key**. A presença de
`OPENROUTER_API_KEY` habilita chamadas de LLM (ex.: planejamento de query) e de
`COHERE_API_KEY` habilita embeddings/rerank comerciais de maior qualidade.
Essa arquitetura garante execução offline com custo zero.

## 6. Estrutura do repositório

```
academy-nvidia-radar/
├── agents/                 # Pipeline multi-agente LangGraph
│   ├── graph.py            # Definição do grafo, roteamento, telemetria
│   ├── state.py            # Dataclasses do estado (AgentState e tipos)
│   ├── llm.py              # Cliente LLM (OpenRouter) com retry/fallback
│   ├── observability.py    # Sink de telemetria NDJSON
│   ├── prompts/            # (reservado) Prompts
│   └── nodes/              # 9 nós: query_planner, retriever, extractor,
│                           #   classifier, evidence_validator, supervisor,
│                           #   nvidia_rag, recommendation, briefing
├── api/
│   └── main.py             # FastAPI: /query, /startups, /candidates, /nurture
├── rag/                    # RAG da base de conhecimento NVIDIA
│   ├── ingest/             # nvidia_kb, chunker, embeddings, ingestor, shared
│   ├── retrieval/          # retriever híbrido, reranker, cache BM25
│   └── eval/               # golden_set, metrics, run_eval, eval_e2e, eval_local
├── scraper/                # (opcional, fora do escopo da entrega)
│   ├── config/settings.py  # Configuração via Pydantic (lê .env)
│   ├── curated_seed.py     # Seed curado: 56 startups (14 ai_native / 40 ai_enabled / 2 non_ai)
│   ├── synthesize_docs.py  # Gera documentos sintéticos para cada startup
│   ├── models.py           # Schemas de dados (StartupCreate, DocumentoCreate)
│   └── pipelines/loaders.py# Loader assíncrono PostgreSQL (upserts)
├── web/                    # Frontend Next.js
│   ├── app/                # page.tsx (query), pipeline/, nurture/, layout
│   ├── components/         # StartupCard, BriefingPanel, NurturePanel, AppShell
│   └── lib/api.ts          # Cliente HTTP tipado para a API
├── tests/
│   └── test_recommendation_scoring.py   # Testes do motor de recomendação
├── data/                   # Diretórios raw/processed/exports (gerados)
├── logs/                   # Telemetria NDJSON por dia (observability)
├── snapshots/              # Capturas/evidências da interface
├── schema.sql              # DDL das tabelas Postgres
├── pixi.toml / pixi.lock   # Ambiente Python (Pixi)
├── docker-compose.yml      # Postgres + Qdrant (opcional, container)
├── pyproject.toml          # Metadados e dependências Python
└── README.md               # Guia de setup e operação
```

## 7. Fluxo de uma consulta (alto nível)

Dada uma consulta em linguagem natural, ex.:
`"AI-native startups de fintech usando LLMs"`:

1. **Query Planner** converte a consulta em keywords, filtros (setor/estágio) e
   uma estratégia de busca.
2. **Retriever** consulta o PostgreSQL via SQL parametrizado (LIKE em
   nome/setor/descrição + filtros) e devolve até 25 startups.
3. **Extractor** lê os documentos textuais de cada startup e extrai perfil
   estruturado: stack, casos de uso, gaps, sinais de IA e sinais de *moat*
   (dados proprietários, profundidade de workflow, modelo custom, distribuição).
4. **Classifier** classifica em `ai_native` / `ai_enabled` / `non_ai` e
   calcula `moat_score`, `inception_fit_score` e `risco_wrapper`.
5. **Evidence Validator** verifica se há evidências (documentos) suficientes
   para sustentar as conclusões.
6. **NVIDIA RAG Agent** consulta a base de conhecimento NVIDIA (busca híbrida +
   rerank) gerando referências por startup.
7. **Recommendation Agent** cruza o perfil com as referências RAG e regras de
   negócio (TAPI §5.5) e produz recomendações priorizadas com justificativas,
   prioridade, complexidade e próxima ação.
8. **Briefing Agent** gera o briefing executivo final (3 ângulos) para a
   melhor startup candidata.

## 8. Diferenciais técnicos

- **RAG com reranking em fallback local**: o sistema funciona offline (sem
  Cohere) com reranker local (cosseno + overlap) mantendo a pipeline completa.
- **Validação de citações (groundedness)**: referências cuja tecnologia não
  aparece no conteúdo do chunk são descartadas antes da recomendação.
- **Scoring normalizado da recomendação**: `0.6 * RAG + 0.25 * regras + 0.15 *
  setor`, com `score_breakdown` por recomendação para auditabilidade.
- **Detecção anti-wrapper**: sinais de LLM wrapper são detectados e sinalizados
  como `risco_wrapper` (não sobrescrevem a categoria).
- **Telemetria por execução**: NDJSON em `logs/telemetry-*.ndjson` com timings
  por nó, uso de tokens, scores pré/pós rerank e efetividade do reranker.

## 9. Documentos relacionados

- `docs/ARQUITETURA.md` — grafo de agentes, dataclasses de estado, fluxo e
  decisões de design.
- `docs/AGENTES.md` — descrição detalhada dos 9 agentes.
- `docs/RAG.md` — ingestão, chunking, retrieval híbrido, reranking, avaliação.
- `docs/BASE_DADOS.md` — schema, seeds e carregamento.
- `docs/ENV.md` — variáveis de ambiente.
- `docs/TESTES.md` — cobertura, execução e baselines.
- `docs/CRIAR_NOVO_AGENTE.md` — guia de extensão da pipeline.