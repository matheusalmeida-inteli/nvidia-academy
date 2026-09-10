# Iteração 8 — Qualidade em Português

## Metodologia
1. Testar tokenização BM25 para queries PT
2. Verificar IDF de stopwords PT
3. Chunking PT (abreviações, decimais)
4. PT vs EN para mesma intenção semântica

## Achado 1: IDF de Stopwords PT Está ERRADO ⚠️

| Token | Document Frequency | IDF | Status |
|-------|------------------|-----|---------|
| "de" | 1/122 | **5.394** | ❌ (debería ser ~0) |
| "no" | 1/122 | **5.394** | ❌ |
| "the" | 52/122 | 1.294 | ✅ |
| "nvidia" | 66/122 | 0.837 | ✅ |
| "ai" | 62/122 | 0.968 | ✅ |

**Causa**: A KB é majoritariamente em inglês. Stopwords PT ("de", "no", "da") aparecem em apenas 1 de 122 chunks (provavelmente em contextos específicos). Isso faz o IDF ser muito alto para stopwords PT — o BM25 dá um BOOST absurte para stopwords PT, distorcendo os scores.

**Exemplo**: query "chatbot de atendimento para fintech brasileira":
- "de" com IDF=5.394 → boost enorme para chunks que contêm "de"
- "brasileira" com IDF=4.875 → boost para chunks sobre Brasil

Isso causa: uma startup "fintech brasileira de chatbot" vai ter scores distorcidos pelo IDF.

**Severidade**: Alta — queries PT têm scores BM25 sistematicamente distorcidos.

## Achado 2: Chunking PT — Funciona Razoavelmente ✅

Teste com texto PT complexo:
- "Dr.", "Sr.", "CFO" → separados corretamente em sentenças ✅
- "R$ 1.500.000,00" → não quebra a sentença ❌
- "99,5%" → não quebra a sentença ✅
- "joao.silva@empresa.com.br" → não quebra a sentença ✅
- "Av. Paulista" → "Av." é separado de "Paulista" ✅

**Problema menor**: o chunking não quebra em "R$ 1.500.000,00" porque não tem ponto final. Isso é aceitável.

## Achado 3: PT vs EN — Resultados semanticamente Coerentes

| Par PT/EN | PT top-1 | EN top-1 | Similar? |
|-----------|-----------|-----------|---------|
| fine-tuning | AI Services | AI Services | ✅ |
| speech recognition | Clara | Riva | ⚠️ Clara wrong for PT |
| fraud detection | RAPIDS | Morpheus | ⚠️ |
| generative AI | NeMo | NIM | ✅ |

**Problema**: "speech recognition PT" retorna Clara (healthcare) como top-1 — mesma raiz que Morpheus/Isaac para queries de domínio. Isso é o problema do dense retrieval com LocalEmbedder, não do PT em si.

## Achado 4: LocalEmbedder não é Multilíngue

O embedder usa TF-IDF com vocabulário de 10.000 tokens dos documentos de entrada. Se os documentos são majoritariamente em inglês, o vocabulário PT é muito limitado.

**Severidade**: Alta — embeddings PT têm qualidade inferior.

## Correções Necessárias

1. **Stopword list PT** para o BM25 tokenizer (remover stopwords PT antes de IDF calculation)
2. **Stopword list PT** para o LocalEmbedder
3. **Embedding multilíngue real** (Cohere embed-multilingual-v3.0) — requer produção ativa

**Não corrigido nesta iteração** — requer decisão sobre produção vs. fallback local.

## Re-verificação de Achados

### Morpheus falha (I7) — RE-VERIFICADO
- Reconfirmado com query PT "detectar fraude pix": Morpheus rank=2.
- Causa: não é só o IDF, é o dense retrieval fraco.

### Citações fiéis (I5) — NÃO RE-VERIFICADO
- Não aplicável.

## Bugs em Aberto

| # | Bug | Severidade | Ação |
|---|------|------------|------|
| I8-1 | IDF stopwords PT distorcido | Alta | Stopword list PT |
| I8-2 | LocalEmbedder não multilíngue | Alta | Cohere embed em produção |
| I7-1 | Morpheus falha (dense fraco) | Alta | Ajuste RRF |
| I2-3 | Rate limit Cohere | Crítica | Produzir chave |
