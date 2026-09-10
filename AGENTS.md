# AGENTS.md — Registro da sessão de implementação

## Objetivo
Implementar os 4 itens de melhoria RAG + análise profunda de placeholders/fallbacks.

## Itens implementados (build confirmado)

1. **Config central (Item 1)**
   - `rag/config.py` criado — fonte única de `chunk_target/max/overlap`, `rrf_*`, `rerank_enabled`, `local_dense_fallback`, etc.
   - Atualizados: `shared.py`, `chunker.py`, `ingestor.py`, `retriever.py`.
   - `.env` completado com todas as vars RAG_*. `.env.example` atualizado.

2. **JSONL extracao (Item 2)**
   - `rag/ingest/data/nvidia_concepts.jsonl` gerado (43 conceitos, 22 techs).
   - `nvidia_kb.py` atualizado: prioridade real > JSONL > sintético; loader com `_load_json_kb()`.
   - CLI `python -m rag.ingest.nvidia_kb --export` adicionada.
   - Teste atualizado (`test_shared_defaults_env_driven`) para validar config.

3. **Fallback denso local (Item 3)**
   - `_dense_local_fallback()` adicionado a `retriever.py`.
   - Cache global `_CORPUS_EMBEDDING_CACHE` + `_corpus_cache_key()`.
   - Quando Qdrant falha, retorna resultados por cosseno sobre chunks locais.

4. **Eval CI (Item 4)**
   - `pixi.toml`: tasks `test`, `test-rag`, `eval`, `eval-local`, `export-kb` (eval/
     eval-local/export-kb rodam via `-m` — corrigido).
   - `rag/README.md`: baseline MRR 0.889, hit_rate@3 1.0, recall@3 0.722, latency_avg 2644ms.
   - Eval local atual: MRR 0.909, hit_rate@1 0.879, hit_rate@3 0.939, latency_avg 825.5ms.

5. **Stub RAG determinístico (bônus)**
   - `tests/test_graph_integration.py`: `_stub_nvidia_rag` com fallback fixo de refs —
     `low_evidence=False` garantido no fluxo nominal. **75 → 81 testes passam.**

## Rodada 2 (esta sessão) — ENTREGAS DO PLANO APROVADO

### Entrega 1 — Qualidade do briefing (audit_iter2 #11, #16)
- `agents/nodes/briefing.py`: `_relevance_score()` combina keywords da `user_query`
  com o perfil da startup; `_top_key` agora ordena por `relevance × fit` (não só fit).
- Ações comerciais contextualizadas: usam `proxima_acao` real da tech + gap alvo.

### Entrega 2 — Teste que falhava
- `test_fluxo_nominal_completo` passa em ambiente sem Qdrant/DB (refs determinísticas).

### Entrega 3 — TECH_DEFS + fallback anti-placeholder (audit_iter2 #13)
- `TECH_DEFS` ganhou `MONAI` e `Omniverse` (cobrindo todas as 22 techs da KB).
- `CANONICAL_NAMES` ganhou `"NVIDIA NeMo"→NeMo` e `"NVIDIA RAPIDS"→RAPIDS`.
- `_proxima_acao_for`: MONAI/Omniverse adicionados nos 3 dicionários (rag/fallback/comunidade);
  fallback default agora é informativo (`Explorar documentação oficial da NVIDIA para <tech>...`).
- `_fallback_def(tech)`: gera justificativa contextual em vez de placeholder genérico.
- Testes anti-placeholder em `tests/test_recommendation_scoring.py::TestAntiPlaceholder`:
  cobertura KB↔TECH_DEFS, ausência de "Tecnologia NVIDIA para X.", e `_fallback_def` informativo.

### Entrega 4 — Spiders de alta prioridade
- `cubo`, `open100`, `ace`, `abstartups`, `anjos`, `darwin` ganharam `CARD_SELECTORS`
  específicos; `open100` parseia `<table><tbody><tr>` (ranking por corporação).
- `scraper/spiders/__init__.py` docstring corrigido ("Spider stubs" era obsoleto).
- `tests/test_spiders.py` criado (6 testes com HTML de exemplo, offline).

## Rodada 4 (esta sessão) — F3 (motor de recomendação) / F4 (resiliência) / F5 (exportação)

### F3a — Expansão do SECTOR_FILTER + matching word-boundary (recommendation.py)
- Helpers `_normalize_text`/`_collapse`/`_sector_match`/`_term_present` + `TEXT_ALIASES`
  (`ia`→inteligencia artificial/ai, `ml`→machine learning) — matching tolerante a acento,
  espaço e hífen; word-boundary evita falso-positivo ("ia" não dispara em "via").
- `SECTOR_FILTER` expandido (fintech/financeiro/seguros, logística/varejo/ecommerce,
  telecom/contact center/bpo, enterprise, marketing/martech, hr/rh/recrutamento,
  educacao/edtech, foodtech, proptech, mobile, games, automotivo, energia, it services,
  impressão 3D, erp, saas + famílias anteriores/imt/rapids/cuml). Cobre todos os setores
  reais das startups de `scraper/curated_seed.py`.
- Filtro em `recommend_for`: techs ancoradas em RAG (`rag_score>=0.5` ou em `rag_evidence`)
  nunca são descartadas; `_compute_sector_boost` usa `_sector_match`.
- +9 testes (`TestSectorExpansion`, `TestWordBoundarySignals`) → 35 em scoring.

### F3b — Fontes canônicas para recs baseadas em regra
- `CANONICAL_SOURCES` (tech → {titulo, url} de docs oficiais NVIDIA) — recs `regra_de_negocio`
  sem fonte RAG agora carregam a fonte canônica em `fontes_rag`.
- `scoring + api_validation` = 42 passed.

### F3c — API + frontend
- `RecommendationItem` (api/main.py) ganhou `evidencias`, `origem_recomendacao`,
  `score_final`, `score_breakdown`, `regra_ids`; tipo `Recommendation` em `web/lib/api.ts`
  expandido; `StartupCard.tsx` renderiza `fontes_rag` (até 2, com link). `npx tsc --noEmit` OK.

### F4 — Resiliência (agents/graph.py)
- `_instrument_node` agora recupera exceções por nó: registra em `state.errors`, loga warning,
  seta `next_agent="briefing"` (degradação graciosa), preserva estado parcial; **briefing nunca
  é engolido** (re-raise). Timing/contagem válidos também em erro (finally).
- Grafo compilado com `compile(checkpointer=MemorySaver())`; `run_pipeline` passa
  `thread_id` novo por run (exigência do checkpointer — sem config, ValueError).
- Teste `test_erro_em_no_degrada_com_estado_preservado` (replan 3x registra 3 erros).
  graph_integration = 5 passed.

### F5 — Exportação de briefing + números + versão
- Endpoint `POST /query/export` (JSON download, reusa o payload de `/query` via
  `_build_query_payload`); botão "Exportar briefing" no frontend (`lib/api.ts::exportBriefing`);
  PDF via Ctrl+P. README/web/README atualizados.
- `page.tsx` corrigido ("56 startups, 224 documentos"); versão unificada **2.1.0**
  (api/main.py + web/package.json).

### Status
- Tests: 77 em `tests/` + 33 em `rag_audit/` = **110**; fast suites verdes.
- Lint (agents/ api/ rag/ scraper/ scripts/): **0 erros**.
- API v2.1.0 com rotas `/query` e `/query/export` registradas.

---
## Rodada 3 (esta sessão) — FASES 1 E 2 (qualidade do produto + RAG)

### Fase 1 — Qualidade do fluxo principal
- 1.1 **Retriever com relevância** (`agents/nodes/retriever.py`): `build_search_query`
  agora devolve `order_sql` com ranking por peso de campo (nome 3.0 > setor 2.0 >
  descricao 1.0), `ORDER BY <score> DESC, id` em vez de `ORDER BY id` (audit_iter3 #23).
  Testes em `tests/test_retriever.py` (3).
- 1.2 **Validação de entrada** (`api/main.py`): `QueryRequest.query` com
  `min_length=1, max_length=500` + `@field_validator` rejeitando espaço em branco;
  `max_startups` em faixa [1,100]. Query vazia → 422 explícito (audit_iter3 #21/#18).
- 1.2b **Fallback de keywords removido** (`agents/nodes/query_planner.py`): em vez de
  mascarar com `["startup","ai","brasil"]`, usa os termos reais da query (2+ chars);
  último recurso `["nvidia"]`.
- 1.3 **Linha morta removida** (`query_planner.py:131`): `parsed = llm.complete_json.__wrapped__`.
- 1.4 **Evidências validadas** (`agents/nodes/evidence_validator.py`, `api/main.py`,
  `web/lib/api.ts`): `evidencias_count` agora usa `n_evidencias_validadas` (peso por
  tipo de doc), não contagem crua de documentos (audit #68). Frontend melhora mensagens
  de erro: 422 → "consulta inválida", 5xx → erro de servidor (audit #67).

### Fase 2 — RAG + evidências
- 2.1 **RAG paralelo** (`agents/nodes/nvidia_rag.py`): consultas por startup via
  `asyncio.gather` + `Semaphore(rag_concurrency)` (default 4) — latência O(n) →
  ~O(ceil(n/4)) (audit_iter7_10 #66).
- 2.2 **`evidence_score` por tipo de documento** (`evidence_validator.py`):
  `DOC_WEIGHTS` (vaga/perfil_founder 1.0, release/careers 0.9, site 0.8, linkedin 0.6,
  noticia/blog 0.5, outro 0.4); `EVIDENCE_THRESHOLD=0.7`. Docs abaixo do threshold não
  contam como evidência verificada; score é capado em 0.3 quando há docs mas nenhuma
  evidência forte (audit_iter4 #35-36).

### Testes
- `tests/test_api_validation.py` (7): validação do QueryRequest + `doc_weight`.
- `tests/test_retriever.py` (3): SQL de busca e ordenação por relevância.

## Rodada 3 (Fase 4) — CLEANUP (lint 100% verde)

### Código morto removido
- `rag/config.py::to_dict()` e `rag/ingest/ingestor.py::idf_score()` — zero chamadas.
- `agents/nodes/recommendation.py::_should_recommend()` — sempre retornava `True`
  (filtro setorial inócuo); removido junto com o `continue` morto no caller e a
  referência em `docs/AGENTES.md`. Filtro setorial efetivo segue via
  `_compute_sector_boost()`.
- Dict morto `iftech_comunidade` em `_proxima_acao_for()` — nunca era usado.
- Variáveis locais não usadas: `n_gaps` (evidence_validator), `stack`
  (nvidia_rag/build_rag_queries), `count` (ingestor.main), `total_docs`
  (curate), `sector` (synthesize_docs).
- Imports não usados: `numpy.typing` (ingestor), `Optional` (query_planner,
  extractor) + ~269 auto-corrigidos pelo `ruff --fix` (imports fora de ordem,
  imports não usados tipo `Source`/`Path`/`EstagioEnum`, F541/F841).
- `run_sync` em `agents/graph.py` foi MANTIDO (documentado em docs/ARQUITETURA.md).

### Higiene
- **`.gitignore` corrigido**: `pg_data/` (era `postgres_data/`) e `qdrant_storage/`
  (era `qdrant_data/`) agora cobertos; adicionados `logs/`, `.qdrant-initialized`,
  `snapshots/`, `baseline_*.json`.
- **Timezones**: `datetime.now()` → `datetime.now(UTC)` (briefing, observability);
  `date.today()` → `datetime.now(UTC).date()` (synthesize_docs).
- **StrEnum**: `class X(str, Enum)` → `class X(StrEnum)` (EstagioEnum,
  DocumentoTipoEnum, SourceCategory, SourceType).
- **Regras do linter** (pyproject.toml): todas as correções mantidas;
  `zip(strict=True)` em evidências/eval (comprimentos garantidos iguais);
  `warnings.warn(stacklevel=2)` (nvidia_kb); `raise ... from e` (api/main).

### Infra
- `pixi.toml`: tasks `lint` e `lint-fix` adicionadas (ruff).

## Status final desta rodada
- **Testes: 91 pass / 0 falha** (`pixi run test`).
- **RAG tests: 16 pass** (`pixi run test-rag`).
- **Lint: 0 erros** (`pixi run lint`).
- **Eval local: MRR 0.909 / hit@3 0.939** (`pixi run eval-local --retrieval --json out.json`).
- **Export KB: 43 conceitos** (`pixi run export-kb`).
- Fontes bloqueadas mantidas `enabled=False` (Distrito, Endeavor, Bossa, Liga, InovAtiva).

---
## Como testar (script de lançamento)
- `bash run_all.sh` — inicializa .env, verifica KB (43 conceitos) e confirma stack.
- `pixi run test` — suite completa (91 pass).
- `pixi run test-rag` — valida testes RAG (16 pass).
- `pixi run lint` — verificação estática (0 erros).
- `pixi run eval-local --retrieval --json out.json` — eval offline.
- `pixi run export-kb` — exporta JSONL da KB atual.