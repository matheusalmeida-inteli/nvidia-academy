# Módulo `api/` — FastAPI bridge

Interface HTTP entre o frontend (e outras ferramentas) e o pipeline
multi-agente + banco PostgreSQL.

Referência dos endpoints: [`docs/BASE_DADOS.md`](../docs/BASE_DADOS.md).

## Endpoints

| Método | Path | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/startups` | Lista startups (filtros por setor, estágio, busca; contagem de docs) |
| POST | `/query` | Executa o pipeline multi-agente (`QueryRequest` → `QueryResponse`) |
| POST | `/candidates` | Cria candidato (upsert por `startup_id`) |
| GET | `/candidates` | Lista candidatos do funil |
| GET | `/candidates/{id}` | Detalhe de candidato |
| PATCH | `/candidates/{id}` | Atualiza candidato (status, notas, nurture, próximas ações) |
| DELETE | `/candidates/{id}` | Remove candidato |
| POST | `/candidates/{id}/nurture` | Registra ação de nurture e atualiza contato |
| GET | `/candidates/{id}/nurture` | Histórico de nurture |
| GET | `/nurture/upcoming` | Candidatos com próxima ação dentro de `N` dias |

## Arquivos

- `main.py` — schemas Pydantic (`BaseModel`), endpoints e builders
  (`_dict`, `_candidate_row`, `_pool`).
- Conexão ao PostgreSQL via `asyncpg` com pool (host/porta/user/senha/db via
  variáveis `POSTGRES_*`, defaults consistentes com `docker-compose.yml`).

## Uso

```bash
pixi run uvicorn api.main:app --port 8000
```

Teste rápido:

```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Startups de healthtech com visão computacional", "max_startups": 5}'
```

Variáveis de ambiente relevantes: ver [`docs/ENV.md`](../docs/ENV.md).