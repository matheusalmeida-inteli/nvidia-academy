# Arquitetura do Sistema

Este documento detalha a arquitetura de software do **NVIDIA Startup AI Radar**:
o grafo de agentes LangGraph, as dataclasses de estado, o fluxo de execução e
as principais decisões de design.

## 1. Visão geral

O núcleo do sistema é um **grafo de estado** (LangGraph `StateGraph`) com 9 nós
de agente, sendo um deles o **supervisor** (hub central). O grafo recebe uma
consulta em linguagem natural e produz, ao final, uma lista de startups
analisadas + recomendações NVIDIA + um *briefing* executivo.

Todos os nós são funções `async` (ou sync) que recebem `AgentState` e retornam
`AgentState` (estado imutável ampliado a cada passo). LangGraph executa os nós
e mantém o grafo de transição.

## 2. Definição do grafo (`agents/graph.py`)

### 2.1 Nós registrados

| Nome do nó              | Função                    | Papel                                  |
|-------------------------|---------------------------|----------------------------------------|
| `query_planner`         | `query_planner`           | Transforma a consulta em critérios (replan expande) |
| `retriever`             | `retriever`               | Busca startups no PostgreSQL (`LIMIT` ajustável) |
| `extractor`             | `extractor`               | Extrai perfis estruturados dos docs    |
| `classifier`            | `classifier`              | Classifica maturidade AI-native        |
| `evidence_validator`    | `evidence_validator`      | Valida evidências das classificações   |
| `supervisor`            | `supervisor`              | **Hub central**: monitora sinais e roteia |
| `nvidia_rag`            | `nvidia_rag`              | Consulta a base RAG NVIDIA (`top_k` ajustável) |
| `recommendation`        | `recommendation`          | Gera recomendações priorizadas         |
| `briefing`              | `briefing`                | Produz o *briefing* executivo          |

### 2.2 Arestas (fluxo de alto nível)

```
entry ─→ query_planner ─→ retriever ─→ extractor ─→ classifier
         ─→ evidence_validator ─→ supervisor (hub central)
                  ├─── nvidia_rag ─→ recommendation ─→ briefing ─→ END
                  ├─── query_planner   (replan: expandir query)
                  ├─── retriever       (retry: LIMIT ampliado)
                  └─── briefing        (degradacão graciosa)
```

### 2.3 Roteamento condicional (Supervisor)

Após `evidence_validator`, o nó **`supervisor`** (hub central) monitora, em
tempo real, sinais do estado e da telemetria e decide o próximo destino:

- **Sinais OK** → rota para `nvidia_rag` (fluxo normal).
- **Retrieval vazio** (0 startups) **com orçamento de replan** → rota para
  `query_planner`, que expande a query (remove filtros restritivos, keywords
  genéricas) e retenta — via `state.expand_query`.
- **Evidência fraca** (`ratio > 0.5` de `valido=False`) **com orçamento de
  replan** → marca `state.low_evidence = True` e rota para `query_planner`.
- **Retriever lento** (latência acumulada `> 4s` na telemetria) **com orçamento
  de retry** → rota para `retriever`, ampliando `state.retriever_limit` (x2) — e
  o `nvidia_rag` passa a usar `state.rag_top_k`.
- **Orçamento esgotado sem resultados** → rota para `briefing` (degradacão
  graciosa, briefing informativo).

O roteamento é feito por aresta condicional `route_supervisor(state)` em
`agents/nodes/supervisor.py`. A decisão é pura e testável (`decide_next`).

**Garantia de terminação:** os laços são limitados por orçamentos no estado —
`replan_count < MAX_REPLANS` (2) e `retry_count < MAX_RETRIES` (1). Ao esgotar
o orçamento sem startup, o supervisor roteia para `briefing`.

**Semântica de baixa evidência preservada:** quando a maioria das evidências é
inválida, o nó `nvidia_rag` verifica `state.low_evidence` e **pula as chamadas
ao RAG externo** (Cohere/Qdrant), emite referências mínimas (`references: []`)
e o `briefing` sinaliza `evidencia_insuficiente=True`. O supervisor mantém esse
sinal, separando **decisão** (supervisor) da **execução** (nó RAG).

### 2.4 Instrumentação (`_instrument_node`)

Cada nó é envolvido por um *wrapper* que mede tempo de execução e contagem de
chamadas, acumulando em `state.telemetry.node_timings` e
`state.telemetry.node_counts`. O wrapper suporta funções assíncronas e
síncronas (`inspect.isawaitable`). A trilha de decisões do supervisor é
registrada em `state.supervisor_actions` e persistida no NDJSON.

### 2.5 Resiliência (F4) — checkpointer + recovery por nó

- **Checkpointer `MemorySaver`**: o grafo é compilado com
  `g.compile(checkpointer=MemorySaver())`. Cada execução do `run_pipeline`
  passa um `thread_id` novo em `config.configurable`, isolando o estado entre
  requisições (checkpoint/resume por run sem colisão).
- **Recovery por nó**: exceções em qualquer nó **não derrubam o pipeline** —
  o wrapper captura, grava `[nome_no] Tipo: msg` em `state.errors`, loga um
  warning, seta `state.next_agent = "briefing"` (degradação graciosa) e preserva
  o estado parcial já produzido. A única exceção é o nó **`briefing`**, que nunca
  é engolido (rede de segurança final — re-raise imediato). Ver teste
  `test_erro_em_no_degrada_com_estado_preservado`.

## 3. Estado (`agents/state.py`)

O estado é um `@dataclass AgentState` contendo canais de leitura escrita ao
longo do grafo:

| Campo                     | Tipo            | Preenchido por            | Descrição                                    |
|---------------------------|-----------------|---------------------------|----------------------------------------------|
| `user_query`              | `str`           | entrada (`run_pipeline`)  | Consulta original do usuário                 |
| `query_result`            | `QueryResult`   | `query_planner`           | Keywords, filtros e estratégia               |
| `retrieved_startups`      | `list[dict]`    | `retriever`               | Startups recuperadas do PostgreSQL           |
| `retrieval_strategy`      | `str`           | `retriever`               | Estratégia usada (`keyword_match`)           |
| `extracted_profiles`      | `list[dict]`    | `extractor`               | Perfis estruturados por startup              |
| `classifications`         | `list[dict]`    | `classifier`              | Categoria, confiança, moat, fit              |
| `evidence_results`        | `list[dict]`    | `evidence_validator`      | Validade, evidências e lacunas               |
| `nvidia_references`       | `list[dict]`    | `nvidia_rag`              | Referências RAG por startup                  |
| `recommendations`         | `list[dict]`    | `recommendation`          | Recomendações por startup + ações comunitárias|
| `briefing`                | `Briefing`      | `briefing`                | Briefing executivo final                     |
| `errors`                  | `list[str]`     | vários                    | Erros tolerados (não fatal)                  |
| `next_agent`              | `str`           | vários                    | Roteamento interno                           |
| `selected_startup`        | `Optional[dict]`| (reservado)               | —                                           |
| `low_evidence`            | `bool`          | `supervisor`              | Sinal de evidência insuficiente              |
| `replan_count`            | `int`           | `supervisor`              | Orçamento de replans gastos                  |
| `retry_count`             | `int`           | `supervisor`              | Orçamento de retries gastos                  |
| `retriever_limit`         | `int`           | `supervisor`              | `LIMIT` SQL do retriever (retry amplia)      |
| `rag_top_k`               | `int`           | `supervisor`              | `top_k` de rerank do RAG externo             |
| `expand_query`            | `bool`          | `supervisor`              | Flag de replan (query_planner expande)       |
| `supervisor_actions`      | `list[str]`     | `supervisor`              | Trilha de auditoria das decisões             |
| `telemetry`               | `Telemetry`     | instrumentação            | Métricas de execução                         |

### 3.1 Dataclasses auxiliares

- **`QueryResult`** — `raw_query`, `keywords`, `filters`, `strategy`.
- **`ExtractedProfile`** — perfil extraído: `nome`, `site`, `descricao`,
  `stack`, `casos_uso`, `gaps_identificados`, `sinais_ai`, e sinais de *moat*
  (`proprietary_data`, `workflow_depth`, `custom_model`, `distribution`).
- **`ClassificationResult`** — `categoria` (`ai_native`/`ai_enabled`/`non_ai`),
  `confianca`, `justificativa`, `evidencia_ai`, `moat_score`, `wrapper_warning`,
  `inception_fit_score`, `fit_breakdown`.
- **`EvidenceResult`** — `valido`, `evidencias`, `lacunas`, `confianca`.
- **`NVIDIAReference`** — `tech`, `title`, `content`, `url`, `score`,
  `relevance_to_gap`.
- **`Recommendation`** — `tecnologia`, justificativas (técnica/negócio),
  `prioridade`, `complexidade`, `proxima_acao`, `evidencias`, `fontes_rag`.
- **`Briefing`** — empresa, setor, maturidade, score, recomendações, próximos
  passos (comercial/técnico/comunitário), fit, warning de wrapper, sugestão de
  nutrição, fontes e flag `evidencia_insuficiente`.

### 3.2 Telemetria (`Telemetry`)

O objeto `Telemetry` coleta, por execução:

- `run_id`, `started_at`, `ended_at`;
- `node_timings` / `node_counts` (por nó);
- `node_token_usage` (modelo, tokens e latência por nó que chama LLM);
- `retrieval_scores_pre_rerank` / `retrieval_scores_post_rerank` (scores por
  consulta RAG);
- `rerank_effectiveness` (fração reordenada e Kendall tau por consulta);
- `evidence_reasons` (por startup: `ok` / `insufficient_evidence` /
  `groundedness`);
- `low_evidence` (flag global).

A trilha de auditoria das decisões do supervisor (`state.supervisor_actions`)
é gravada junto de cada registro, permitindo rastrear replans/retries/briefing
gracioso por execução.

A persistência é feita em `agents/observability.py`:
**`logs/telemetry-YYYYMMDD.ndjson`**, um arquivo com uma linha JSON por execução.
`run_pipeline` chama `submit_result(result)` após concluir, protegido por
try/except (falha de telemetria não quebra a execução).

## 4. Execução da pipeline (`run_pipeline`)

```python
async def run_pipeline(user_query: str) -> AgentState:
    initial_state = AgentState(user_query=..., next_agent="query_planner")
    initial_state.telemetry.run_id = uuid4().hex[:12]
    initial_state.telemetry.started_at = time.time()
    result = await pipeline.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": uuid.uuid4().hex}},
    )
    # popula ended_at, low_evidence e persiste telemetria
```

- `pipeline` é o grafo compilado no módulo (`build_graph().compile(checkpointer=MemorySaver())`).
  A configuração `thread_id` é exigida pelo checkpointer (um valor novo por run).
- `run_sync` é um wrapper síncrono via `asyncio.run` (útil em scripts).

## 5. LLM (`agents/llm.py`)

`LLMClient` consome a OpenRouter (padrão `anthropic/claude-3-haiku`):

- **Disponibilidade** é definida pela presença de `OPENROUTER_API_KEY`.
- Chamadas com **retry exponencial 0s/1s/2s** apenas para erros transitórios
  (408, 429, 5xx) e erros de rede/timeout.
- `last_usage` / `last_latency_ms` expõem telemetria por chamada
  (`last_call_stats()`).
- `complete_json` parseia JSON com tolerância a *code blocks* e extração do
  primeiro objeto/lista.

Quando o LLM não está disponível, os agentes usam heurísticas determinísticas
(ex.: `heuristic_parse` no planner, regras no classifier). O sistema portanto
nunca depende de uma API externa para executar.

## 6. Observabilidade (`agents/observability.py`)

`TelemetrySink` grava uma linha NDJSON por execução em
`logs/telemetry-<data>.ndjson`. O registro inclui: runtime em segundos, query,
timings por nó, token usage, scores pré/pós rerank, efetividade do reranker,
`evidence_reasons`, flag de baixa evidência, número de startups e de
recomendações e erros. Isso permite auditoria das decisões e análise de
custo/latência por execução.

## 7. Interface entre o grafo e a API

O módulo `api/main.py` expõe o endpoint `POST /query` que chama
`run_pipeline(req.query)`, converte o `AgentState` (`result.__dict__`) em
`QueryResponse` (Pydantic) e devolve:

- `startups[]`: cada item com nome, metadados, `categoria`, `confianca`,
  `inception_fit_score`, `wrapper_warning`, `moat_score`, `evidencias_count` e
  `recomendacoes[]`;
- `briefing`: o briefing executivo (ou `null`);
- `query_keywords` e `total_found`.

O mapeamento `_dict()` normaliza tanto dataclasses quanto dicts, garantindo que
a API funcione independentemente da forma interna do estado.

## 8. Decisões de design relevantes

1. **Estado único tipado**: todo o contexto da execução viaja em `AgentState`
   (dataclass), o que torna o grafo rastreável e serializável.
2. **Fallback determinístico em todos os agentes**: o pipeline funciona sem
   LLM, sem Cohere e sem internet (exceto para acesso ao PostgreSQL/Qdrant
   locais). Isso é crítico para demonstração e CI.
3. **Roteamento baseado em evidência**: se a maioria das startups não tem
   documentos suficientes, o RAG é pulado e o briefing assume a incerteza
   explicitamente, preservando a honestidade do resultado.
4. **Validação de groundedness no RAG**: `validate_citations` filtra
   referências em que a tecnologia não aparece no conteúdo do chunk,
   impedindo recomendações não suportadas pelo conhecimento baseado.
5. **Telemetria como requisito, não extra**: timings, tokens, scores e razões
   de evidência são persistidos em NDJSON — alimenta decisões de qualidade e o
   relatório do vídeo/apresentação.