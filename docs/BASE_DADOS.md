# Base de Dados (PostgreSQL)

Este documento descreve o schema Postgres, o conteúdo pré-populado (seed) e os
mecanismos de carregamento do projeto. O PostgreSQL é a fonte de dados da
pipeline (via Retriever), do CRM de nurture (via API FastAPI) e recebe os
documentos sintéticos que alimentam o Extractor.

## 1. Schema (`schema.sql`)

O DDL está em `schema.sql` e contém 4 tabelas. O schema é idempotente
(`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).

### 1.1 Tabela `startups`

Startups brasileiras pré-populadas (a base curada).

| Coluna            | Tipo      | Restrições                                    |
|-------------------|-----------|-----------------------------------------------|
| `id`              | SERIAL    | PK                                            |
| `uuid`            | UUID      | `gen_random_uuid()` UNIQUE NOT NULL           |
| `nome`            | TEXT      | NOT NULL                                      |
| `site`            | TEXT      |                                               |
| `setor`           | TEXT      |                                               |
| `estagio`         | TEXT      | CHECK: `pre-seed`, `seed`, `serie_a`…`serie_later`, `desconhecido` |
| `localizacao`     | TEXT      |                                               |
| `descricao_curta` | TEXT      |                                               |
| `ano_fundacao`    | INT       | CHECK 1990–2030                               |
| `tamanho_time`    | INT       | CHECK > 0                                     |
| `fontes_scraping` | TEXT[]    | default `{}`                                  |
| `created_at` / `updated_at` | TIMESTAMPTZ | default `NOW()`                     |

### 1.2 Tabela `documentos`

Conteúdo textual **não estruturado** por startup — a matéria-prima do
Extractor. Garante a rastreabilidade pedida no **TAPI §5.2** via `url_fonte`.

| Coluna            | Tipo      | Restrições                                |
|-------------------|-----------|-------------------------------------------|
| `id`              | SERIAL    | PK                                        |
| `uuid`            | UUID      | `uuid_generate_v4()` UNIQUE NOT NULL      |
| `startup_id`      | INT       | FK → `startups.id` ON DELETE CASCADE      |
| `tipo`            | TEXT      | CHECK: `site_institucional`, `blog`, `noticia`, `vaga`, `perfil_founder`, `release`, `careers`, `linkedin`, `outro` |
| `titulo`          | TEXT      |                                           |
| `conteudo_texto`  | TEXT      |                                           |
| `url_fonte`       | TEXT      | NOT NULL                                  |
| `data_publicacao` | DATE      |                                           |
| `source_meta`     | JSONB     | default `{}`                              |
| `created_at`      | TIMESTAMPTZ | default `NOW()`                        |
|                   |           | UNIQUE(`startup_id`, `url_fonte`)         |

**Uso na pipeline:** o Extractor busca até 3 documentos por startup
(`titulo` + `conteudo_texto`) concatenados para extração do perfil; se não
houver documentos, cai para `descricao_curta`.

### 1.3 Tabela `candidates`

CRM do ciclo **Atrair → Qualificar → Nutrir** (TAPI §1). Um registro por
startup. Escrita pela API FastAPI e pré-preenchida na consulta `/query`.

| Coluna                 | Tipo       | Restrições                                  |
|------------------------|------------|---------------------------------------------|
| `id`                   | SERIAL     | PK                                          |
| `startup_id`           | INT        | FK → `startups.id` ON DELETE CASCADE, UNIQUE |
| `inception_fit_score`  | REAL       | default 0.0                                 |
| `status`               | TEXT       | `identificado`, `contatado`, `engajado`, `onboarding`, `declined` (default `identificado`) |
| `categoria_ai`         | TEXT       | `ai_native`, `ai_enabled`, `wrapper_llm`, `non_ai`, `desconhecido` |
| `wrapper_warning`      | BOOLEAN    | default FALSE                               |
| `fit_justification`    | TEXT       |                                             |
| `moat_score` / `tech_score` / `sector_score` / `traction_score` | REAL | breakdown 0–1 |
| `nurture_cadence`      | TEXT       | `semanal`, `quinzenal`, `mensal`, `inativo` |
| `next_action_date`     | DATE       |                                             |
| `next_action_type` / `next_action_desc` | TEXT |                              |
| `notes`, `assigned_to`, `last_contacted_at`, `last_contacted_type` | | CRM extras |
| `source_query`         | TEXT       | Query que originou o candidato              |
| `created_at` / `updated_at` | TIMESTAMPTZ | default `NOW()`                     |

### 1.4 Tabela `nurture_log`

Histórico de engajamento de cada candidato.

| Coluna         | Tipo      | Restrições                                |
|----------------|-----------|-------------------------------------------|
| `id`           | SERIAL    | PK                                        |
| `candidate_id` | INT       | FK → `candidates.id` ON DELETE CASCADE    |
| `action_type`  | TEXT      | CHECK: `email`, `call`, `meetup`, `gtc`, `workshop`, `demo_day`, `linkedin`, `introduction`, `pitch`, `follow_up` |
| `channel`      | TEXT      | `email`, `call`, `whatsapp`, `linkedin`, `in_person`, `event`, `online` |
| `outcome`      | TEXT      | `positive`, `negative`, `no_response`, `scheduled`, `pending` |
| `notes`        | TEXT      |                                           |
| `created_at`   | TIMESTAMPTZ | default `NOW()`                       |

### 1.5 Índices

- `startups`: setor, estagio, localizacao;
- `documentos`: startup_id, tipo, data_publicacao;
- `candidates`: status, next_action_date, inception_fit_score DESC, startup_id;
- `nurture_log`: candidate_id, action_type, outcome.

## 2. Seed curado (`scraper/curated_seed.py`)

A base pré-populada é um **seed curado manualmente** — não há scraping na
entrega final (fora do escopo). A estrutura:

```python
AI_NATIVE       = [...]   # startups core AI como produto
AI_ENABLED      = [...]   # IA augmenta negócio existente
AI_NATIVE_PURE  = [...]   # complemento do primeiro grupo
ALL_STARTUPS    = list unique por Nome (case-insensitive)
```

**Dados reais de `ALL_STARTUPS`:**

| Categoria    | Quantidade |
|--------------|------------|
| `ai_native`  | 14         |
| `ai_enabled` | 40         |
| `non_ai`     | 2          |
| **Total**    | **56**     |

> **Nota:** o `README.md` cita "52 startups" (obsoleto). O número correto é
> **56** (aplicando o dedupe da lista `ALL_STARTUPS`).

Cada registro contém `nome`, `site`, `setor`, `estagio`, `localizacao`,
`ano_fundacao`, `tamanho_time`, `categoria` e `descricao_curta` (dados
públicos reais).

O `categoria` do seed é usado pelo Extractor (`_CURATED_CAT`) como atributo
`categoria` no perfil e pelo Classifier apenas como **ajuste de confiança**
(+0.10 em concordância, −0.15 em divergência) — a classificação final vem da
análise textual, não do seed.

## 3. Síntese de documentos (`scraper/synthesize_docs.py`)

Para que as startups tenham conteúdo para o Extractor, o projeto gera
**documentos sintéticos** por startup (descrições, notícias e vagas), com
5 tipos de sinais determinísticos por categoria:

- `PROPRIETARY_DATA_SIGNALS` — dados proprietários (bloqueado por setor):
  ex.: "mais de 50M de registros históricos", "dataset único de imagens
  médicas com 200K+ laudos";
- `WORKFLOW_DEPTH_SIGNALS` — profundidade de workflow/MLOps;
- `CUSTOM_MODEL_SIGNALS` — modelos custom (fine-tuning, CNN custom, ensemble);
- `NVIDIA_RELEVANCE_SIGNALS` — contexto específico de techs NVIDIA;
- `SINAIS_IA_GERAIS` — sinais gerais de IA.

Regras de geração:
- **1º documento**: sempre concreto (`casos_uso_1`), apenas vedações impeditivas
  (milita (não pode haver) — se `categoria` depende: `non_ai` não recebe
  sinais fortes).
- **2º documento**: tipo escolhido do mesmo conjunto, sem repetição de texto.
- **3º documento**: garantido para `ai_native`; para `ai_enabled` apenas se
  sorteio < 0.8; `non_ai` não recebe 3º documento.
- Data de publicação: agora − `random.randint(10, 240)` dias.
- Seeds aleatórios com `random.Random(seed_int)` para reprodutibilidade.

Execução com DB conectado:

```bash
pixi run python -m scraper.synthesize_docs
```

## 4. Loader (`scraper/pipelines/loaders.py`)

`DatabaseLoader` — loader assíncrono com **upsert**:

- Pool `asyncpg.create_pool` (min 1, max `scraper_max_concurrency * 2`).
- `upsert_startup` → `INSERT ... ON CONFLICT (LOWER(nome)) DO UPDATE`
  (seed idempotente por nome case-insensitive).
- `upsert_documento` → `INSERT ON CONFLICT (startup_id, url_fonte)
  DO NOTHING` (idempotente por fonte).
- Usado por `scraper/run.py`, `synthesize_docs.py` e pelo módulo da API
  (`DatabaseLoader` compartilhado como singleton para leitura no Retriever e
  nos endpoints de candidates/nurture).

## 5. Configuração de conexão

Padrões (`scraper/config/settings.py` e `api/main.py`):

| Variável          | Default             |
|-------------------|---------------------|
| `POSTGRES_HOST`   | `127.0.0.1`         |
| `POSTGRES_PORT`   | `5432`              |
| `POSTGRES_USER`   | `nvidia_radar`      |
| `POSTGRES_PASSWORD`| `nvidia_radar_pass` |
| `POSTGRES_DB`     | `nvidia_radar`      |

> Obs.: `api/main.py` usa uma configuração própria (lê as mesmas variáveis,
> valores padrão iguais). A pipeline também aceita uma **URL única**
> `DATABASE_URL` quando `config/settings.py` está habilitado.

## 6. Populando/validando o banco

```bash
# 1) Aplicar schema (via Postgres local ou container)
psql -h 127.0.0.1 -U nvidia_radar -d nvidia_radar -f schema.sql

# 2) Carregar as 56 startups
pixi run python -m scraper.curated_seed          # imprime total e categorias
pixi run python -m scraper.synthesize_docs       # gera documentos + fará upsert

# 3) Verificar
pixi run python -c "from scraper.pipelines.loaders import DatabaseLoader; ..."
```

O `docker-compose.yml` sobe `postgres:16-alpine` montando `schema.sql` em
`/docker-entrypoint-initdb.d/`, aplicando o schema automaticamente na primeira
subida:

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_USER: nvidia_radar
    POSTGRES_PASSWORD: nvidia_radar_pass
    POSTGRES_DB: nvidia_radar
  volumes:
    - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro
```

## 7. Fluxo de dados resumido

```
curated_seed.py ──► ALL_STARTUPS (56) ──► synthesize_docs.py ──► DatabaseLoader
                                                                    │ upsert
                                                                    ▼
   Retriever ◄── query ── PostgreSQL (startups + documentos) ──► API /candidates
                                                              ──► web (nurture)
```

- Leitura na pipeline: `Retriever` (SELECT limit 25), `Extractor` (documents),
  `/startups`, `/candidates`, `/nurture`.
- Escrita: `synthesize_docs`, `POST /query` (create candidate),
  `PATCH /candidates/{id}`, `POST /candidates/{id}/nurture`,
  `DELETE /candidates/{id}`.