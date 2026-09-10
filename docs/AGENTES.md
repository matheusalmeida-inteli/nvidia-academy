# Agentes do Sistema Multi-Agente

Este documento descreve os 9 agentes (nós) da pipeline LangGraph, incluindo o
supervisor (hub central), e o nó
auxiliar de roteamento. Para cada agente: propósito, entradas, saídas,
decisões e comportamento de fallback.

Todos os agentes estão em `agents/nodes/*.py` e são registrados em
`agents/graph.py`.

## Índice dos agentes

| # | Agente                 | Arquivo                    | Saída principal                       |
|---|------------------------|----------------------------|---------------------------------------|
| 1 | Query Planner          | `query_planner.py`         | `QueryResult` (keywords, filtros, estratégia) |
| 2 | Retriever              | `retriever.py`             | `retrieved_startups`                  |
| 3 | Extractor              | `extractor.py`             | `extracted_profiles`                  |
| 4 | Classifier             | `classifier.py`            | `classifications`                     |
| 5 | Evidence Validator     | `evidence_validator.py`    | `evidence_results`                    |
| 6 | NVIDIA RAG             | `nvidia_rag.py`            | `nvidia_references`                   |
| 7 | Recommendation         | `recommendation.py`        | `recommendations`                     |
| 8 | Briefing               | `briefing.py`              | `briefing`                            |

---

## Agente 1 — Query Planner (`query_planner.py`)

**Propósito (TAPI §5.1):** transformar a consulta em linguagem natural em
critérios de busca estruturados (keywords, filtros de setor/estágio) e definir
a estratégia de análise.

**Entradas:** `state.user_query`.

**Saída:** `state.query_result` (dataclass `QueryResult`) e
`state.next_agent = "retriever"`.

**Comportamento:**
- Consultas com menos de 3 caracteres usam keywords padrão `["startup", "ai",
  "brasil"]`.
- **Com LLM** (`OPENROUTER_API_KEY`): chama `llm.complete` pedindo JSON
  (`keywords`, `filters`, `strategy`) com `response_format=json_object`; se o
  parse falhar, cai em heurística. Telemetria de tokens é registrada em
  `state.telemetry.node_token_usage["query_planner"]`.
- **Sem LLM**: `heuristic_parse` detecta setor (via `SECTOR_KEYWORDS`, ex.:
  fintech, healthtech, edtech, proptech, agtech, iot, cybersec, speech, ai),
  estágio (`STAGE_KEYWORDS`: pre-seed, seed, série A/B/C), foco em IA e extrai
  até 5 keywords genéricas (com stopwords).

**Decisão-chave:** escolha entre parsing por LLM ou heurística determinística,
garantindo que o pipeline funcione offline.

---

## Agente 2 — Retriever (`retriever.py`)

**Propósito (TAPI §5.1):** consultar a base pré-populada (PostgreSQL) e
selecionar as startups relevantes para a consulta.

**Entradas:** `state.query_result`.

**Saída:** `state.retrieved_startups` (listas de dicts) com
`SELECT id, nome, site, setor, estagio, localizacao, descricao_curta,
ano_fundacao, tamanho_time` — **LIMIT 25**.

**Comportamento:**
- `build_search_query(query_result)` monta SQL parametrizado (sem SQL injection):
  - OR de LIKE (case-insensitive) sobre `nome`, `setor`, `descricao_curta`
    para cada keyword;
  - `LOWER(setor) LIKE %X%` quando o filtro `setor` existe;
  - `estagio = X` quando o filtro `estagio` existe;
  - sem critérios → `1=1`.
- Conecta via `DatabaseLoader` (pool asyncpg) e executa o SELECT.
- Falhas de banco são registradas em `state.errors` (não fatais) e o nó segue
  para o próximo agente mesmo sem resultados.

**Decisão-chave:** combinação de filtros estruturados com busca textual difusa
(LIKE), mantendo a consistência com o dicionário de keywords do planner.

---

## Agente 3 — Extractor (`extractor.py`)

**Propósito (TAPI §5.1):** transformar o conteúdo textual não estruturado
(descrições, trechos de sites etc.) em **dados estruturados** sobre a empresa e
sua stack, incluindo sinais de *moat* (TAPI §1 anti-wrapper).

**Entradas:** `state.retrieved_startups`.

**Saída:** `state.extracted_profiles` — um dict por startup com: `nome`,
`site`, `setor`, `estagio`, `localizacao`, `descricao`, `stack` (até 10),
`casos_uso` (até 5), `gaps_identificados` (até 5), `sinais_ai` (até 10),
`proprietary_data`, `workflow_depth`, `custom_model`, `distribution`,
`wrapper_indicators`, `tamanho_time`, `categoria` (curada via
`scraper/curated_seed.py`).

**Mecânica:**
- Busca até **3 documentos** por startup (`titulo` + `conteudo_texto`),
  concatenados; se não houver documentos, usa `descricao_curta`.
- `extract_from_text` executa **match por dicionários**:
  - `AI_SIGNALS` (~60 termos: LLM/gpt/rag/vector db/nlp/ocr/mlops/gpu/cuda/etc.);
  - `TECH_KEYWORDS` (linguagens, frameworks, infra, stack NVIDIA);
  - padrões de regex → `casos_uso` (customer service, fraud detection, RAG,
    speech AI, predictive analytics, medical diagnosis etc.);
  - heurísticas de `gaps_identificados` (uso de APIs externas sem otimização,
    custo de inferência, latência, falta de GPU, governança, privacidade);
  - sinais de *moat*: `PROPRIETARY_DATA_SIGNS`, `WORKFLOW_SIGNS`,
    `CUSTOM_MODEL_SIGNS`, `DISTRIBUTION_SIGNS`;
  - `WRAPPER_SIGNS` (wrapper de openai/gpt, "powered by openai", prompts
    pré-feitos etc.).

**Decisão-chave:** a presença de sinais de *moat* é o que alimenta a detecção
anti-wrapper e o cálculo de `moat_score` no Classifier.

---

## Agente 4 — Classifier (`classifier.py`)

**Propósito (TAPI §5.1 / §1):** classificar a maturidade AI-native e estimar o
fit para o programa NVIDIA Inception, com detecção anti-wrapper.

**Entradas:** `state.extracted_profiles`.

**Saída:** `state.classifications` — por startup: `categoria`
(`ai_native`/`ai_enabled`/`non_ai`), `confianca`, `justificativa`,
`evidencia_ai` (5 sinais), `moat_score`, `risco_wrapper`, `inception_fit_score`,
`fit_breakdown`.

**Subcomponentes:**

| Função                  | Descrição                                                     |
|-------------------------|---------------------------------------------------------------|
| `_compute_moat`         | `moat_score` (0–5) a partir de dados proprietários (≤2.0), workflow (≤1.5), modelo custom (≤2.0), distribuição (≤1.0); penalidades por indicadores de wrapper, ausência de modelo próprio (−0.4) e ausência de dados próprios (−0.3) |
| `_is_llm_wrapper`       | `risco_wrapper` bool — combina `wrapper_indicators`, `moat < 1.5`, termos de API de LLM (openai/langchain), ausência de modelo privo e dados próprios |
| `_sector_score`         | Setor estratégico para NVIDIA (peso 0.4–0.9 por keyword)       |
| `_tech_score`           | Nível de adoção de tech NVIDIA (sinais_ai + stack + descrição), normalizado por 4 |
| `_traction_score`       | Sinais de mercado: time size, "milhões", "clientes", B2B/enterprise, tração, investidores |
| `_inception_fit_score`  | Score agregado 0–1: 30% moat + 30% tech + 15% setor + 20% tração + bônus; retorna `fit_breakdown` |

**Lógica de categoria (por prioridade):**
1. `native_score >= 3 AND moat >= 2.5` → `ai_native`.
2. `native_score >= 3 AND moat >= 1.5` → `ai_enabled` (alto uso de AI, moat
   moderado).
3. Sinais nativos ("ai agent", "generative", "llm platform", "ai-native") →
   `ai_enabled` (moat < 2.5) ou `ai_native`.
4. `enabled_score >= 3` com sinais/casos/stack reais → `ai_enabled`.
5. `enabled_score >= 2` com sinais → `ai_enabled` (confiança 0.55).
6. senão → `non_ai`.

**Decisão importante:** `categoria` do seed é usada **apenas como ajuste de
confiança** (+0.10 se concorda, −0.15 se diverge) e **nunca sobrescreve** a
categoria inferida por texto — o Classifier tem poder preditivo próprio.

---

## Agente 5 — Evidence Validator (`evidence_validator.py`)

**Propósito (TAPI §5.1):** validar se as afirmações extraídas possuem evidências
(documentos) e fontes suficientes na base.

**Entradas:** `state.extracted_profiles` + `state.classifications`.

**Saída:** `state.evidence_results` — por startup: `name`, `valido`
(bool), `evidencias` (até 5 com `titulo`, `url`, `tipo`), `lacunas`,
`confianca`.

**Critério de validade (`valido`):**
```
evidence_score = min(1.0, (n_docs / 3) * 0.5 + (n_ai_signals / 5) * 0.4 + 0.1)
valido = n_docs >= 1 and evidence_score > 0.3
```

**Lacunas:** < 3 documentos (nota sobre mínimo para alta confiança) e ausência
de sinais de IA numa empresa não `non_ai`.

**Relação com o grafo:** o resultado alimenta o **supervisor**, que roteia para
`query_planner` (replan expande a query) quando > 50% das startups têm
`valido=False` e há orçamento de replan; caso contrário, marca
`state.low_evidence=True` e segue para o `nvidia_rag`.

---

## Agente 6 — NVIDIA RAG (`nvidia_rag.py`)

**Propósito (TAPI §5.1):** consultar a base de conhecimento NVIDIA via retrieval
híbrido + reranking e devolver as referências mais relevantes para os gaps de
cada startup.

**Entradas:** `state.extracted_profiles` (+ `state.low_evidence`).

**Saída:** `state.nvidia_references` — por startup: `name`, `references`
(até 5), `invalid_refs`.

**Comportamento:**
- `build_rag_queries(profile)` gera até 3 queries (ver `docs/RAG.md §8.1`).
- Para cada query: `HybridRetriever.retrieve(q, top_k_rerank=2)` com retry
  (0/1/2s); registra telemetria de scores pre/post rerank e efetividade.
- Dedupe por tech (melhor score); `validate_citations` (groundedness) descarta
  techs sem suporte no conteúdo do chunk.
- `low_evidence=True` → pula o RAG e emite referências vazias.

**Decisão-chave:** filtrar referências por groundedness evita "alucinação" de
recomendação sem suporte na KB (melhoria documentada nos evals).

---

## Agente 7 — Recommendation (`recommendation.py`)

**Propósito (TAPI §5.1 / §5.5):** cruzar o perfil da startup com as
referências NVIDIA (RAG) e com regras de negócio, gerando recomendações
priorizadas e ações de comunidade.

**Entradas:** `state.extracted_profiles`, `state.classifications`,
`state.nvidia_references`.

**Saída:** `state.recommendations` — por startup: `name`, `categoria`,
`confianca`, `risco_wrapper`, `moat_score`, `inception_fit_score`,
`fit_breakdown`, `recomendacoes[]`, `community_actions[]`.

### Motor de scoring (normalizado)

```
score = RAG_WEIGHT * rag_component
      + HARDCODED_WEIGHT * hardcoded_component
      + SECTOR_WEIGHT * sector_component
       RAG_WEIGHT     = 0.60
       HARDCODED_WEIGHT = 0.25
       SECTOR_WEIGHT  = 0.15
```

- `rag_component` = rerank_score da tech (via referências, > 0.2);
- `hardcoded_component` = 1.0 se alguma `TechRule` disparar;
- `sector_component` = 1.0 se `_compute_sector_boost` casar.

`MIN_FINAL_SCORE = 0.20`; máximo de 6 recomendações; `score_breakdown`
(`rag`/`hardcoded`/`sector`) é exposto por recomendação.

### Regras de negócio (`TECH_RULES`)
12 regras mapeiam sinais do extractor para techs NVIDIA (TAPI §5.5). Cada regra
exige `requires_all` (todos os termos no texto) **e** `requires_any_of`
(pelo menos um) **ou** `sector_boost`, o que elimina disparos com keyword
solta (ex.: "ml" sozinho não recomenda RAPIDS/cuML).

| Regra                     | Requisitos-chave                      | Techs recomendadas              |
|---------------------------|---------------------------------------|---------------------------------|
| `grandes_volumes_tabulares` | ml + (predictive/analytics/hf/tf/kafka/airflow) | RAPIDS, cuDF, cuML |
| `llm_atendimento_wrapper`  | llm + (atendimento/nlp) + `risco_wrapper` | NIM, NeMo Guardrails, Triton |
| `llm_inferencia_producao`  | llm + (mlops/tensorrt/triton)         | NIM, TensorRT-LLM, Triton       |
| `llm_fine_tuning_custom`   | llm + (hf/tf/modelo de ml)            | NeMo, NIM                       |
| `rag_retrieval`            | llm + (rag/retrieval)                 | NIM, NeMo                       |
| `voz_callcenter`           | ia + (asr/tts/speech/voz/áudio)       | Riva, NIM                       |
| `imagens_medicas_saude`    | ia + (imagens médicas/diagnóstico/clara/monai) | Clara, MONAI, NIM   |
| `robotica_simulacao`       | gpu + (robótica/isaac/omniverse/ros2) | Isaac, Omniverse                |
| `cybersec_ameacas`         | ml + (cybersec/fraude/anomalias)      | Morpheus, RAPIDS                |
| `governanca_agentes`       | llm + (governança/compliance/guardrails) | NeMo Guardrails, NIM        |
| `generative_ai_llm_ops`    | llm + (generativa/gpt/langchain)      | NIM, NeMo, TensorRT-LLM         |
| `gpu_treinamento_custom`   | gpu + (cuda/treinamento in-house)     | CUDA, RAPIDS                    |

### Mecânica da recomendação (`recommend_for`)
1. Pool de techs = referências RAG (score > 0.2) ∪ regras disparadas.
2. Para cada tech: computa `score`, filtra por `MIN_FINAL_SCORE`, classifica
   `origem`:
   - `rag_e_regra` (RAG + regra), `rag` (só RAG), `regra_de_negocio` (só
     regra), `fraca`.
   - Evidência RAG = `rag_component >= 0.5` **ou** presença de content no chunk
     (robustez no modo fallback onde scores tendem < 0.5).
3. Ordena por score; **consolida famílias** (`_consolidate_families`):
   `accelerated_data` (RAPIDS/cuDF/cuML) e `llm_runtime` (NIM/NeMo/TensorRT-LLM)
   mantêm apenas o membro de maior score.
4. Monta output: justificativa técnica (texto RAG se disponível, senão
   `TECH_DEFS`), justificativa de negócio, `prioridade`/`complexidade` de
   `TECH_DEFS`, `proxima_acao` variando por origem/regra/tech
   (`_proxima_acao_for`: ações RAG profundas vs. fallback de pesquisa),
   `evidencias`, `fontes_rag` e `score_breakdown`.

### Ações de comunidade (`community_actions_for`)
Gera até 4 ações comunitárias por categoria/fit/moat/setor/estágio, incluindo
nurture para `risco_wrapper` (ex.: workshop "Como construir defensibilidade",
sessão "de wrapper para AI-native").

**Decisão-chave:** o RAG é o sinal primário (peso 0.6), mas regras de negócio
e setor garantem recomendações úteis mesmo quando o RAG fallback tem scores
baixos — sempre rotulando a `origem` para auditoria.

---

## Agente 8 — Briefing (`briefing.py`)

**Propósito (TAPI §2.6):** gerar o *briefing* executivo em **3 ângulos** —
comercial, técnico e comunitário — para o gerente de Startups & VCs.

**Entradas:** `state.recommendations`, `state.extracted_profiles`,
`state.classifications`, `state.evidence_results`, `state.low_evidence`.

**Saída:** `state.briefing` (dataclass `Briefing`).

**Comportamento:**
- Sem recomendações → *briefing* vazio informativo com dicas de query.
- Seleciona a startup **top** por `inception_fit_score`, com tiebreak por
  `confianca` e favorecendo empresas sem `wrapper_warning`.
- Constrói recomendações (dataclass `Recommendation`) e consolida `fontes_rag`
  (TAPI §5.3 rastreabilidade).
- Próximos passos:
  - **Comerciais**: descoberta focada na tech top; proposta formal de Inception
    conforme fit (≥0.65 formal, 0.4–0.65 exploratório, <0.4 educar);
    conversa de defensibilidade se `wrapper_warning`.
  - **Técnicos**: POC por tech (NIM/Triton/TensorRT-LLM → benchmark
    latência/custo; RAPIDS/cuDF/cuML → workshop hands-on; NeMo Guardrails →
    POC de segurança; Riva → POC de ASR/TTS PT-BR); alerta de evidência
    insuficiente se `low_evidence`.
  - **Comunitários**: ações de `community_actions` (meetups, Inception Capital
    Connect, GTC, peer intro por setor) com fallback padrão.
- Cadência de nutrição por estágio (`_cadence_for`: quinzenal para
  pre-seed/seed, mensal para A/B/C) e data da próxima ação
  (`_next_action_date_for`).
- `nurture_suggestion` condensa a estratégia (wrapper → educação; fit alto →
  mix técnico+comercial; fit moderado → construir sinais de moat).

---

## Supervisor (hub central — `supervisor.py`)

**Propósito (TAPI §6, diferencial):** monitorar, em tempo real, sinais do
estado e da telemetria e decidir **continuar / replan / retry / degradacão
graciosa**, com back-edges no grafo LangGraph.

**Entradas:** `state.retrieved_startups`, `state.evidence_results`,
`state.replan_count`, `state.retry_count`, `state.low_evidence` e
`state.telemetry.node_timings["retriever"]`.

**Decisão (`decide_next` — função pura):**
- retrieval vazio (0 startups) com orçamento de replan → `query_planner`;
- evidência >50% inválida com orçamento de replan → marca `low_evidence` e
  `query_planner`;
- retriever lento (>4s acumulado) com orçamento de retry → `retriever`
  (LIMIT x2, `top_k` de RAG ampliado);
- orçamento esgotado sem resultados → `briefing` (gracioso).

**Garantia de terminação:** `MAX_REPLANS=2`, `MAX_RETRIES=1` —
`replan_count`/`retry_count` limitam os laços no estado.

**Saída:** `state.next_agent`, `state.replan_count`, `state.retry_count`,
`state.retriever_limit`, `state.rag_top_k`, `state.expand_query` (flag de
replan consumida pelo `query_planner`) e `state.supervisor_actions` (trilha de
auditoria persistida no NDJSON).

**Roteamento:** aresta condicional `route_supervisor(state)` em `graph.py`
(hub-and-spoke).

---

## Nó auxiliar — roteamento (`graph.py`)

- `route(state)`: rota pelo campo `next_agent` (usado como roteador genérico).
- `route_supervisor(state)`: aresta condicional do hub — devolve
  `state.next_agent` para `nvidia_rag`, `query_planner`, `retriever` ou
  `briefing` (ver `docs/ARQUITETURA.md §2.3`).