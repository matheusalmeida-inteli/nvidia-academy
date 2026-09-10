# Módulo `agents/` — Pipeline multi-agente (LangGraph)

Orquestração dos 9 nós que transformam uma consulta em texto em um briefing
executivo com recomendações de tecnologia NVIDIA, com um supervisor central
que decide retry/replan/degradacão graciosa em tempo real.

Detalhamento completo: [`docs/AGENTES.md`](../docs/AGENTES.md).

## Estrutura

| Arquivo | Papel |
|---|---|
| `state.py` | Tipos do grafo: `QueryResult`, `ExtractedProfile`, `ClassificationResult`, `EvidenceResult`, `NVIDIAReference`, `Recommendation`, `Briefing` e `AgentState` |
| `graph.py` | Monta o grafo LangGraph (hub-and-spoke com supervisor) e expõe `run_pipeline(query)` |
| `llm.py` | Cliente de LLM (OpenRouter/API) com `complete`/`complete_json`; `is_available()` indica se há backend configurado |
| `observability.py` | Telemetria: soma de tokens por nó, registro NDJSON por evento e trilha `supervisor_actions` |
| `prompts/` | Diretório reservado para prompts de sistema |
| `nodes/` | Implementação dos 9 nós |

## Nós (`agents/nodes/`)

| Nó | Responsabilidade |
|---|---|
| `query_planner.py` | Interpreta a consulta e gera palavras-chave de busca (replan expande filtros) |
| `retriever.py` | Busca startups candidatas no PostgreSQL (SQL com filtros e `LIMIT` ajustável) |
| `extractor.py` | Extrai o perfil da startup (setor, maturidade, descrição) do texto dos documentos |
| `classifier.py` | Classifica maturidade AI, categoria, detecta wrapper e calcula Inception fit score |
| `evidence_validator.py` | Valida evidências e filtra ruído das páginas |
| `supervisor.py` | **Hub central**: monitora telemetria/evidência e decide `nvidia_rag` (continuar), `query_planner` (replan), `retriever` (retry) ou `briefing` (degradacão graciosa) |
| `nvidia_rag.py` | Chama o `HybridRetriever` e valida citações (groundedness) |
| `recommendation.py` | Aplica a tabela de regras + justificativa RAG e define prioridade/próxima ação |
| `briefing.py` | Monta o briefing final (cadência, próximos passos, fontes) |

## Como funciona

Cada nó recebe e produz um `AgentState` (imutável no LangGraph). Quando não há
LLM configurado, os nós usam heurísticas/regras (fallback determinístico). A
telemetria de cada nó é gravada como NDJSON para diagnóstico de latência/custo.

O **supervisor** roda após `evidence_validator` e roteia dinamicamente:
- **Sinais OK** → `nvidia_rag` (fluxo normal);
- **Retrieval vazio ou evidência >50% inválida** → `query_planner` (replan expande a query, remoção de filtros);
- **Retriever lento (>4s)** → `retriever` (retry com `LIMIT` ampliado);
- **Orçamento esgotado sem resultados** → `briefing` (degradacão graciosa).

Os laços são limitados por orçamento no estado (`replan_count <= MAX_REPLANS`,
`retry_count <= MAX_RETRIES`), garantindo terminação. Quando a maioria das
evidências é inválida, o supervisor marca `state.low_evidence=True` e o
`nvidia_rag` pula chamadas ao RAG externo, preservando a semântica original.

## Uso

```bash
pixi run python -c "import asyncio; from agents.graph import run_pipeline; print(asyncio.run(run_pipeline('AI-native fintech usando LLMs')))"
```

## Testes

- `tests/test_recommendation_scoring.py` cobre a tabela de regras e o scoring.
- `tests/test_supervisor.py` cobre as decisões do supervisor (retry/replan/briefing/limite de orçamento).
- `rag_audit/` valida regressão e melhorias do RAG.

```bash
pixi run pytest tests/test_supervisor.py tests/test_recommendation_scoring.py -q
```