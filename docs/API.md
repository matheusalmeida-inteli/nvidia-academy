# API — NVIDIA Startup AI Radar

Documentação dos endpoints da API FastAPI (`api/main.py`). Versão **2.1.0**.

## Base URL

Local: `http://localhost:8000`  
Via Docker: ver `docs/DEPLOY.md`

---

## Endpoints

### `GET /health`

Healthcheck. Resposta: `{"status":"ok","service":"nvidia-radar-api","version":"2.1.0"}`

---

### `GET /startups`

Lista startups com filtros opcionais.

| Query | Tipo | Descrição |
|---|---|---|
| `setor` | `str` | Filtro parcial no setor |
| `estagio` | `str` | Filtro exato no estágio |
| `search` | `str` | Busca parcial no nome |
| `limit` | `int` | Padrão `20`, máx `100` |
| `offset` | `int` | Paginação |

Resposta: lista de startups + total + `documentos` (contagem vinculada).

---

### `POST /query`

Executa o pipeline multi-agente e retorna startups enriquecidas + briefing.

**Request body (`QueryRequest`):**

```json
{
  "query": "startup AI saúde Brasil",
  "max_startups": 10
}
```

Validações: `query` entre 1 e 500 chars (espaço em branco retorna `422`); `max_startups` entre 1 e 100.

**Resposta (`QueryResponse`):**

- `startups`: lista de `StartupResult` (nome, setor, categoria, confiança, `inception_fit_score`, `wrapper_warning`, `recomendacoes`...)
- `briefing`: `BriefingResponse` (maturidade AI, scores, `nurture_suggestion`, próximas ações comerciais/técnicas/comunitárias)
- `query_keywords`: termos extraídos
- `total_found`: quantidade de startups recuperadas

---

### `POST /query/export`

Idêntico a `/query`, mas retorna `application/json` com `Content-Disposition: attachment` (`briefing_nvidia_radar.json`). Útil para exportação 1-click do briefing executivo (requisito TAPI §6).

---

### Candidatos (Pipeline / Nurture)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/candidates` | Lista candidatos (filtros: `status`, `categoria_ai`, `assigned_to`, `limit`, `offset`). Ordenado por `inception_fit_score` DESC |
| `POST` | `/candidates` | Cria candidato (`CandidateCreate`: `startup_id`, `notes`, `assigned_to`). Faz upsert (`ON CONFLICT`) |
| `GET` | `/candidates/{candidate_id}` | Busca candidato por ID (`404` se não existir) |
| `PATCH` | `/candidates/{candidate_id}` | Atualiza campos enviados (`CandidateUpdate`: `status`, `notes`, `assigned_to`, `next_action_*`, `nurture_cadence`) |
| `DELETE` | `/candidates/{candidate_id}` | Remove candidato. Retorna `{"deleted": true/false}` |

---

### Nurture Log

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/candidates/{candidate_id}/nurture` | Registra ação (`NurtureLogEntry`: `action_type`, `channel`, `outcome`, `notes`). Se `outcome == "positive"`, atualiza `last_contacted_at` e `last_contacted_type` |
| `GET` | `/candidates/{candidate_id}/nurture` | Histórico de nurture (mais recente primeiro) |
| `GET` | `/nurture/upcoming?days=7` | Candidatos com `next_action_date <= CURRENT_DATE + days` (exclui `declined`, `onboarding`) |

---

## Modelos principais (Pydantic)

- `RecommendationItem`: tecnologia, justificativa técnica/negócio, prioridade, complexidade, `fontes_rag`, `evidencias`, `score_final`, `regra_ids`
- `StartupResult`: nome, site, setor, estágio, localização, categoria, `inception_fit_score`, `wrapper_warning`, `recomendacoes`
- `BriefingResponse`: empresa, setor, `maturidade_ai`, `score_maturidade`, `nurture_suggestion`, próximas ações, fontes RAG
- `CandidateResponse`: id, `startup_id`, `startup_nome`, `inception_fit_score`, `moat_score`, scores por dimensão (`tech/sector/traction`)
- `NurtureLogResponse`: id, `candidate_id`, `action_type`, `channel`, `outcome`, `notes`, `created_at`

---

## Erros

- `422`: validação de request (query vazia, `max_startups` fora do intervalo)
- `404`: candidato não encontrado
- `500`: falha no pipeline multi-agente (logado com `logger.error`)

---

## Como rodar

```bash
# Com pixi (recomendado)
pixi run start-api   # se definido; caso contrário:
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Sem pixi (virtualenv direto)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Variáveis de ambiente: ver `docs/ENV.md` (`POSTGRES_*`, `QDRANT_*`, etc.).
