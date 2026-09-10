# Iteração 2 — Profundidade Quantitativa

## Metodologia
- 30 queries de teste (domínio misto: lexical, denso, específico)
- Análise da contribuição BM25 vs dense no RRF
- Distribuição de scores do Cohere Rerank
- Validação da correção IDF (iteração 1)

## Achado 1: BM25 contribui significativamente (Bug Corrigido Confirmado)

**Após correção do IDF**, BM25 contribui exclusivamente em **19/30 queries** (63%).
- Queries "puras" de nome de tecnologia (ex: "Triton inference server kubernetes", "Riva speech ASR Portuguese Brazil") são dominadas por BM25.
- Dense domina em 7/30 (23%) — casos onde a query tem mais semântica implícita.
- Overlap (ambos contribuem no top-5): apenas 0.3 items avg — as duas buscas retornam rankings quase inteiramente diferentes.

**Conclusão**: BM25 é **não decorativo** — contribui de forma decisória em 63% das queries.

**Métricas de IDF corrigido** (verificadas após correção):
| Token | IDF | Interpretação |
|--------|------|------|
| "clara" | 3.18 | Raro → boost alto ✅ |
| "riva" | 3.48 | Raro → boost alto ✅ |
| "for" | 0.00 | Comum → sem boost ✅ |
| "and" | 0.00 | Comum → sem boost ✅ |
| "nvidia" | 0.84 | Moderado ✅ |

## Achado 2: Cohere Rerank — Scores discriminam bem, mas bimodal

Distribuição de 39 scores de rerank (15 queries × 3 results, com 6 rate limit failures):

| Range | Count |
|-------|-------|
| >=0.8 | 17/39 (44%) |
| 0.6-0.8 | 5/39 (13%) |
| 0.4-0.6 | 1/39 (3%) |
| 0.2-0.4 | 1/39 (3%) |
| <0.2 | 6/39 (15%) |

- min=0.000, max=1.000, avg=0.711, stdev=0.391
- P10=0.009, P50=0.992, P90=1.000

**Conclusão**: Cohere discrimina bem. Mas os scores muito concentrados em 1.0 indicam que muitas queries retornam matches quase-perfeitos, o que pode não ser informativo para desempate.

## Achado 3: Cohere Rate Limit — Crítico

**Bug encontrado**: Cohere Trial key limitada a **10 chamadas por minuto**.
- Teste: 15 queries sequenciais → 6 falhas (40%) com erro HTTP 429.
- Pipeline típico: 56 startups × 3 queries de RAG × 1 rerank = **168 chamadas/mínimo** em produção.
- Isso significa que o pipeline vai falhar massivamente com a chave Trial.

**Severidade**: Crítica.
**Observação**: O fallback para `RerankFallback` (local) funciona corretamente quando o Cohere falha (caught in `try/except` no `retriever.py:115-120`). Mas:
1. O fallback local (0.7×cos + 0.3×overlap) pode produzir rankings significativamente diferentes do Cohere.
2. Não há mecanismo de cache entre chamadas — cada startup faz 3+ chamadas de rerank.

**Não corrigido nesta iteração**: requer decisão sobre chave de produção vs. otimização do fallback local.

## Achado 4: Qdrant 43 docs → 122 chunks — chunking funciona

- 43 parent docs → 122 chunks (ratio 2.84 chunks/doc)
- Chunk sizes: min=151, avg=471, max=821 chars
- Chunking semântico ativo (usa `LocalEmbedder` para breakpoints) — não decorativo.

## Re-verificação de Achados da Iteração 1

### 1. IDF quebrado (Bug #2 da it1) — RE-VERIFICADO ✅
- Antes: IDF sempre 1.0 (`.__rpow__(1)`).
- Depois: IDF correto (log-based Robertson-Sparck Jones).
- Confirmado com tokens reais: "clara"=3.18, "riva"=3.48, "for"=0.0, "and"=0.0.
- **Estável: confirmado por método diferente (tokens reais vs. math check).**

### 2. Cohere nunca ativo (Bug #3 da it1) — RE-VERIFICADO ✅
- Antes: `RerankFallback` sempre ativo.
- Depois: `CohereRerank` ativo (via `get_settings()`).
- Confirmado por inspeção direta: `type(reranker).__name__ == 'CohereRerank'`.
- **Estável: confirmado por chamada real (benchmark de 3 queries).**

### 3. KB sintética (Achado #1 da it1) — NÃO RE-VERIFICADO
- Não coberto nesta iteração (requer inspeção de conteúdo de chunks).
- **Pendente: necessário medir se a KB sintética gera viés no golden set.**

### 4. LocalEmbedder em produção (Achado #2 da it1) — NÃO RE-VERIFICADO
- Verificado que embeddings dos chunks vão para Qdrant via fallback local.
- **Pendente: o `CohereEmbedder` tenta API mas cai no fallback — só `HybridRetriever` corrige o Rerank, não o Embedder.**

## Bugs Corrigidos na Iteração 2
Nenhum bug de código novo corrigido. Bugs da iteração 1 validados como corrigidos.

## Achados em Aberto

| # | Achado | Severidade | Status |
|---|--------|------------|--------|
| I1-1 | KB sintética (não fontes reais) | Alta | Aberto |
| I1-2 | LocalEmbedder em produção (Qdrant) | Alta | Aberto |
| I2-3 | Cohere rate limit (10/min Trial) | **Crítica** | Aberto |
| I2-4 | Scores Cohere bimodais (muitos 1.0) | Baixa | Aberto |
