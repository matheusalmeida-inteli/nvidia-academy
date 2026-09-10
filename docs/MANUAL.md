# MANUAL — NVIDIA Startup AI Radar

Manual de uso para operadores / analistas de startup.

---

## O que é

Plataforma multi-agente que consulta uma base de startups brasileiras + conhecimento NVIDIA, classifica fit, gera briefing executivo e recomenda tecnologias (RAG híbrido + pipeline LangGraph).

---

## Como consultar (Frontend / API)

1. Acesse `http://localhost:3000` (dev) ou URL de produção.
2. Digite uma query (ex: `startup AI saúde Brasil` — mínimo 1 char, máximo 500).
3. Ajuste `max_startups` (padrão 10, máx 100).
4. Clique em consultar.

Resultado: cards de startups + briefing consolidado (fit, maturidade AI, recomendações tecnológicas com fontes RAG, próximas ações comerciais/técnicas).

---

## Exportar briefing

Botão **"Exportar briefing"** (ou `POST /query/export`) gera `briefing_nvidia_radar.json`. Pode ser impresso via Ctrl+P para PDF.

---

## Pipeline multi-agente (resumo)

1. **Query Planner**: extrai keywords, valida entrada (rechça vazio → 422)
2. **Retriever**: busca startups + documentos (relevância por campo: nome > setor > descrição)
3. **Extractor / Classifier**: classifica categoria, score de fit (`inception_fit_score`), `wrapper_warning`
4. **Evidence Validator**: valida evidências por tipo (`DOC_WEIGHTS`; threshold 0.7)
5. **NVIDIA RAG**: consulta base NVIDIA (`nvidia_knowledge`) — híbrido dense + BM25 + rerank
6. **Recommendation**: gera recomendações técnicas (`RecommendationItem`) com fontes canônicas se sem RAG
7. **Briefing**: consolida briefing executivo (maturidade AI, nurture, próximas ações)

---

## Candidatos / Nurture

- Criar candidato (`POST /candidates`) vinculado a uma startup.
- Atualizar status, notas, responsável, próximas ações (`PATCH`).
- Registrar nurture (`POST /candidates/{id}/nurture`): canal, desfecho (`positive`/`scheduled`/`negative`), notas.
- Se `outcome == positive` → atualiza `last_contacted_at` e `last_contacted_type`.
- Listar próximos (`GET /nurture/upcoming?days=7`): candidatos com ação próxima.

---

## Interpreting scores

- `inception_fit_score`: 0–1. Quanto maior, melhor fit com NVIDIA Inception.
- `wrapper_warning = true`: risco de ser wrapper / não ter tecnologia própria (ver `fit_breakdown`).
- `moat_score`: força competitiva estimada.
- `confianca`: confiança da classificação (baseada em evidências validadas).
- `score_maturidade`: maturidade AI da startup.

---

## Avaliação RAG (offline)

```bash
pixi run eval-local --retrieval --json out.json
# MRR ≈ 0.909, hit@3 ≈ 0.939, latência média ≈ 825ms
```

Se precisar restaurar KB: `pixi run export-kb` (43 conceitos, 22 techs).
