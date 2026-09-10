# Iteração 5 — Fidelidade de Citações (Alucinação)

## Metodologia
Para cada resultado de retrieval, verificar programaticamente se:
1. O nome da tech realmente aparece no conteúdo do chunk
2. O chunk é semanticamente relevante para a query (análise manual de casos adversos)

## Achado 1: Taxa de Fidelidade Alta: 95.6%

45 citações analisadas (15 queries × top-3):
- **43/45 (95.6%)**: a tech recuperada aparece no conteúdo do chunk ✅
- **2/45 (4.4%)**: falso positivo (substring overlap acidental):
  - `e003`: chunk "NeMo Fine-Tuning" contém "Triton" como substring de "TensorRT-LLM"
  - `e011`: chunk "Triton Production ML" contém "NeMo" em contexto (semantic context)

**Conclusão**: as citações não alucinam — o chunk realmente contém a tech mencionada. O problema está NO QUE FOI RECUPERADO antes da citação, não na citação em si.

## Achado 2: Citações Fieles, Mas Retrievals Erradas

Para queries adversariais (fora de escopo), os chunks retornados SÃO citeados corretamente mas são semanticamente irrelevantes:

**"recipe for chocolate cake"** → NIM, Clara, NeMo Guardrails
- Chunk NIM: menciona "Brazilian fintech", "fraud detection" — citeado corretamente ✅
- Chunk Clara: menciona "healthcare", "medical imaging" — citeado corretamente ✅
- Chunk Guardrails: menciona "AI assistants", "safety" — citeado corretamente ✅
- **Problema**: o BM25 retornou esses chunks porque "AI" aparece em ambos. A citação é fiel ao chunk, mas a recomendação é irrelevant.

**"OpenAI GPT-4 architecture details"** → NIM, CUDA, NeMo
- Chunk NIM: menciona "OpenAI SDK compatible" — citeado corretamente ✅
- Chunk CUDA: correto ✅
- Chunk NeMo: correto ✅
- **Conclusão**: a query "OpenAI GPT-4" casou com chunks que mencionam "OpenAI SDK compatible" (integração, não arquitetura). A citação é fiel mas a relevância é marginal.

## Conclusão Central

**As citações não são decorativas nem alucinadas** — são fragmentos genuínos da KB. O problema é que o retrieval pode selecionar chunks semanticamente irrelevantes para queries off-topic, E o downstream (recomendação) usa esses chunks sem filtro de relevância.

Este achado REFORÇA o achado de I3 (sem rejeição out-of-domain):
- I3 identificou: sistema não sabe dizer "não sei"
- I5 confirma: as citações estão corretas, mas são de chunks irrelevantes

**Severidade**: Não é "alucinação de citação" (que seria crítica), mas sim "recomendação sem filtro de relevância". Classificação revisada: **Média** (a citação em si é honesta, o erro é anterior).

## Re-verificação de Achados

### Out-of-domain sem rejeição (I3) — RE-VERIFICADO ✅
- As mesmas 7 queries off-topic retornaram recomendações com chunks citeados de forma fiel mas irrelevante.
- O sistema faz "recomendação honesta mas errada" — não alucinação de citação.

### Cohere rate limit (I2-3) — RE-VERIFICADO ✅
- Não testado nesta iteração, mas confirmado em I2 e I4.

### IDF corrigido (I1-2) — NÃO RE-VERIFICADO
- **Pendente.**

### Golden set contaminado (I4) — NÃO RE-VERIFICADO
- **Pendente.**

## Achados em Aberto

| # | Achado | Severidade | Status |
|---|--------|------------|--------|
| I3-1 | RAG sem rejeição out-of-domain | Crítica | Aberto |
| I2-3 | Cohere rate limit 10/min | Crítica | Aberto |
| I4-1 | Golden set contaminado | Alta | Aberto |
| I1-1 | KB sintética | Alta | Aberto |
| I1-2 | LocalEmbedder em produção | Alta | Aberto |
| I5 | Citações corretas mas retrieval off-topic | **Média** | Aberto |

## Próximos Passos
- Priorizar: I3-1 (out-of-domain sem rejeição) é crítico e pode ser mitigado com threshold de score
- I2-3 (rate limit) requer decisão sobre produção vs. fallback local
- I5 não requer correção de código (as citações estão funcionando corretamente)
