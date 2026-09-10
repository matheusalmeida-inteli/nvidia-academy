# DEPLOY — NVIDIA Startup AI Radar

Como subir o sistema para produção / ambiente de integração.

---

## Requisitos

- **Python** >= 3.11 (gerenciado via `pixi.toml` / `.pixi/`)
- **PostgreSQL** >= 15 (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`)
- **Qdrant** >= 1.7 (coleção `nvidia_knowledge`, 384 dims, host/porta configuráveis)
- **Node.js** >= 20 (para `web/`)
- Opcional: **Docker Compose** (`docker-compose.yml` no root do projeto)

---

## Variáveis de ambiente (`.env`)

Copiar `.env.example` → `.env` e preencher. NUNCA commitar `.env` (já ignorado).

Principais grupos:

- `POSTGRES_*` (DB estrutural — startups, candidatos, nurture)
- `QDRANT_*` (vector store — KB NVIDIA)
- `COHERE_API_KEY` (opcional; se vazio usa fallback local TF-IDF + rerank)
- `RAG_*` (configuração do pipeline: chunk_target, rrf_params, rerank_enabled, concurrency)
- `NEXT_PUBLIC_API_URL` (frontend → API)

Ver `docs/ENV.md` para descrição completa de cada variável.

---

## Passo a passo (manual)

### 1. Banco de dados

```bash
# Criar DB + usuário
createdb nvidia_radar
psql -d nvidia_radar -f schema.sql   # se houver
```

`schema.sql` está na raiz do projeto. Confirma tabelas: `startups`, `documents`, `candidates`, `nurture_log`.

### 2. Qdrant (KB NVIDIA)

```bash
# Se Qdrant não estiver rodando
qdrant --snapshot /caminho/para/snapshots/nvidia_knowledge/...
# Ou via Docker
# Ver docs/ENV.md para QDRANT_HOST/PORT
```

Verificar se a coleção `nvidia_knowledge` existe e tem embeddings de 384 dimensões.

### 3. Instalar dependências Python

```bash
pixi install
# ou
pip install -e .
# ou (conforme pyproject.toml / requirements)
pip install -r requirements.txt  # se existir
```

### 4. Rodar API

```bash
pixi run start-api  # se definido; caso contrário:
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Healthcheck: `curl http://localhost:8000/health`

### 5. Rodar frontend

```bash
cd web/
npm ci
npm run dev    # dev server
npm run build  # produção
npm start      # serve .next
```

Configurar `NEXT_PUBLIC_API_URL=http://localhost:8000` no `.env.local`.

---

## Docker Compose (opcional)

`docker-compose.yml` define stack completa (Postgres + Qdrant + API + Web). Ajustar `.env` antes de subir.

```bash
docker compose up -d
```

---

## Verificações antes de subir

- [ ] `python -m pytest tests/ rag_audit/` passa (110 testes)
- [ ] `pixi run lint` = 0 erros
- [ ] `.env` não está no stage (`git status` não deve listar)
- [ ] `snapshots/` e `logs/` estão ignorados (já no `.gitignore`)
- [ ] `data/exports/` contendo `articles.jsonl`, `startups.jsonl` está ok para versionar (não são grandes; `data/raw/` é ignorado)
- [ ] `web/package-lock.json` e `package.json` consistentes

---

## Atualizações / rollbacks

- Versão unificada: `api/main.py` = `2.1.0`; `web/package.json` = `2.1.0`
- Exportar KB: `pixi run export-kb` (gera `nvidia_concepts.jsonl` com 43 conceitos)
- Avaliação RAG offline: `pixi run eval-local --retrieval --json out.json`
