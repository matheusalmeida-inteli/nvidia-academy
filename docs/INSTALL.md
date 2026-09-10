# INSTALL — NVIDIA Startup AI Radar

Como instalar o ambiente de desenvolvimento local.

---

## Pré-requisitos

- Python 3.11+
- Pixi (recomendado) ou pip + venv
- PostgreSQL (opcional — pipeline funciona sem DB para testes unitários; necessário para candidatos/nurture)
- Qdrant (opcional — se indisponível, usa fallback local TF-IDF + rerank, mas com menor precisão)

---

## Instalação com Pixi (recomendado)

```bash
cd academy-nvidia-radar
pixi install
pixi shell
```

O `.pixi/envs/default` é criado automaticamente (`.gitignore` já o ignora).

---

## Instalação com pip (alternativa)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
# Se `pyproject.toml` exigir build extras:
pip install -r requirements.txt  # se definido
```

---

## Configuração (`.env`)

```bash
cp .env.example .env
# Editar .env com suas credenciais (POSTGRES, QDRANT, COHERE_API_KEY se disponível)
```

Nunca versionar `.env`. `docs/ENV.md` descreve cada variável.

---

## Dependências do frontend (`web/`)

```bash
cd web/
npm ci
```

O `.env.local` já existe (não versionar). Ajustar `NEXT_PUBLIC_API_URL` se necessário.

---

## Verificar instalação

```bash
# Python
python -c "import agents.graph; print('Pipeline OK')"

# Testes
pixi run test        # todos
pixi run test-rag    # só RAG (16 testes)

# Lint
pixi run lint

# API (rápido)
pixi run start-api  # ou uvicorn direto
curl http://localhost:8000/health
```

---

## Problemas comuns

- `ModuleNotFoundError` → `pixi install` não rodou; ver `.pixi/envs/default/lib/python3.11/site-packages/`
- `COHERE_API_KEY` vazia → fallback local ativado; MRR ≈ 0.89 em vez de ≈ 0.91 (aceitável para dev)
- Qdrant não responde → `rag/retriever.py` usa `_dense_local_fallback()` (embeddings locais em cache)
- Postgres não conecta → candidatos/nurture falham com `500`; pipeline `/query` ainda funciona (retrieval por arquivos)
