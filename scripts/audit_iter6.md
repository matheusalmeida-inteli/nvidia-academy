# Audit Iter 6 — Diversidade e Ranking

**Data:** 2026-08-29  
**Escopo:** Qualidade do RAG, ranking, diversificação de recomendações

## Descobertas críticas (P0)

### 47. RAG retorna bons resultados mas NÃO são usados nas justificativas
- **Evidência:** RAG para "Dasa health" → Clara=0.317 (relevante!), RAG para "Nubank fintech" → Morpheus=0.245 (relevante!)
- **Mas** `recommend_for` usa `rag_techs` apenas para filtrar (score > 0.2), não para ordenar ou personalizar
- **Impacto:** O RAG tem dados corretos mas as justificativas são do TECH_DEFS estático

### 48. BM25 só fitted em 6 docs de 69 chunks
- **Causa:** `self.bm25.fit(get_chunked_texts())` — o corpus é de 69 chunks, não de todos os docs NVIDIA KB
- **INFO:** `Embedder fitted on 6 documents` — isso é 6 PARENT docs, não 69 chunks
- **Impacto:** Coverage do RAG é muito limitada — o BM25 só tem 1033 tokens de vocabulário

### 49. RAG deduplica por `title` (não por tech)
- **Causa:** `key = doc.get("title", str(id(doc)))` — dois chunks do mesmo doc têm o mesmo title
- **Problema:** Se a mesma tech aparece em 2 chunks, só o primeiro é contado no RRF
- **Resultado:** RAG pode perder signals de uma tech que aparece em múltiplos chunks

### 50. Recomendações não são ordenadas por relevância setorial
- **Causa:** `all_techs = sorted(rag_techs | matched_techs)` — sem ordenação
- **Resultado:** Ordenação é por ordem de inserção (RAG primeiro, depois TECH_MAPPING, depois SECTOR_TECH)

## Descobertas altas (P1)

### 51. NVIDIA AI Enterprise recomendada para TODOS os setores (sem diferenciação)
- **Causa:** Não existe em `TECH_MAPPING`, não tem setor específico
- **Sintomas:** "AI Enterprise: Plataforma enterprise com suporte SLA" — não contextualiza para o setor

### 52. RAPIDS nunca recomendada apesar de estar no SECTOR_TECH
- **Causa:** Não aparece em `TECH_MAPPING`, só em `SECTOR_TECH["fintech"]`
- **Para fintech:** `matched_techs` inclui RAPIDS via `SECTOR_TECH["fintech"]`
- **Mas** tech não tem `TECH_DEFS` → usa fallback → "Tecnologia NVIDIA para RAPIDS"
- **Fallback não descreve o que RAPIDS faz**

### 53. Techs duplicadas: "Morpheus" vs "NVIDIA Morpheus" vs "AI-Native Services" vs "AI Services"
- **Causa:** RAG retorna "NVIDIA Morpheus", TECH_MAPPING gera "Morpheus"
- **Resultado:** UI mostra 2-4 techs que são a mesma coisa
- **Correção:** Canonical name mapping

### 54. RAG com embedder local (sem Cohere) tem baixa qualidade
- **Fallback:** `RerankFallback` — embedding TF-IDF
- **BM25:** fit em 69 chunks com vocabulário pequeno
- **Resultado:** Scores são ruins (0.2-0.3 range) — cobertura limitada

## Descobertas médias (P2)

### 55. "No GPU optimization in current stack" não significa o que parece
- **Causa:** O gap é adicionado quando o texto não menciona "cuda" ou "gpu"
- **Mas** isso NÃO significa que a startup PRECISA de GPU — pode ser que use API
- **Resultado:** Todas as startups recebem o mesmo gap genérico

### 56. Limite de 6 techs é arbitrário
- **Causa:** `recommendations[:6]` hardcoded
- **Problema:** Setores com mais techs relevantes perdem as de prioridade menor

## Ações para I7+
1. **Usar RAG score e title para gerar justificativas reais**
2. **Canonical name mapping** para deduplicar techs
3. **Filtrar por setor**: Clara só para healthcare, Isaac só para robótica
4. **Adicionar TECH_DEFS para RAPIDS, AI Enterprise, AI Services**
5. **Testar RAG com embedder real** (Cohere) vs fallback
