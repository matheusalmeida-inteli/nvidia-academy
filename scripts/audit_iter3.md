# Audit Iter 3 — Casos de Borda e Edge Cases

**Data:** 2026-08-29  
**Escopo:** Edge cases, SQL injection, validação de entrada, robustez

## Descobertas críticas (P0)

### 18. Query vazia retorna "startup ai brasil" — 13 startups sem sentido
- **Causa:** `heuristic_parse` → `if not keywords: keywords = ["startup", "ai", "brasil"]`
- **Impacto:** Usuário sem input recebe output aparentemente "válido" mas sem sentido
- **Comportamento:** Retorna 13 startups e briefing de Huma.AI (primeira)
- **Correção:** Retornar erro ou empty state quando query < 3 chars

### 19. Query planner detecta setor errado
- **Causa:** `SECTOR_KEYWORDS` mapeia para `fintech` mas DB tem `Fintech` (capitalizado). Query planner adiciona `keywords=["fintech"]` + `filters["setor"]="fintech"`. O `LIKE %{fintech}%` não funciona porque DB tem `Fintech` capitalizado.
- **Cenário:** Query "fintech" gera filtro `setor='fintech'` → `LIKE '%fintech%'` — não acha "Fintech"

### 20. Estágio detection é broken
- **Causa:** DB tem estágios em `serie_a`, `seed`, `serie_c`, `desconhecido` (snake_case) mas `STAGE_KEYWORDS` busca por "série a" (com acento)
- **Impacto:** Filtro de estágio NUNCA funciona

## Descobertas altas (P1)

### 21. No validation on user_query in API endpoint
- **Causa:** `QueryRequest` só valida tipo, não conteúdo
- **Impacto:** Queries vazias, com whitespace, etc. passam direto

### 22. SQL LIKE com keywords gera `%keyword%` — partial match fraco
- **Causa:** `params.append(f"%{kw.lower()}%")` — com `%` no início e fim, busca substring anywhere
- **Problema:** "nvidia" matcha "NVIDIA", mas "vidia" tb. Não respeita boundaries
- **Não é bug de segurança** (parametrizado), mas reduz precisão

### 23. Retriever retorna LIMIT 25 sem ordenação por relevância
- **Causa:** `ORDER BY id` — ordem de inserção no banco
- **Impacto:** Se há 30 startups de fintech, retorna sempre as mesmas 25 primeiras
- **Não há ordenação por fit, setor, ou match score**

### 24. Briefing para 0 startups retorna "N/A" — mas ainda gera briefing
- **Comportamento atual:** `build_briefing` retorna briefing vazio com `empresa="N/A"`
- **Melhoria:** Retornar `briefing: null` quando não há startups, com mensagem clara

## Descobertas médias (P2)

### 25. Keywords de stopword são português-only
- `"startup", "startups", "brasileiras"` — stopwords só em português
- Query em inglês ("AI-native fintech Brazil") gera keywords desnecessárias

### 26. Overflow de keywords não é limitado
- `keywords.extend([w for w in words if w not in stopwords][:5])` — limita a 5 mas o LLM parser pode retornar lista ilimitada
- Sem validação de tamanho máximo

### 27. Recursão infinita em `query_planner` se LLM disponível
- **Causa:** `llm.complete_json.__wrapped__` é código interno (não deve ser chamado assim)
- **Trecho problemático:**
  ```python
  raw = await llm.complete(system, user, response_format=...)
  parsed = llm.complete_json.__wrapped__  # ← isso é código CPython interno, não有用
  ```
  Mas como está em `try`, não quebra. Porém a variável `parsed` nunca é usada!

## Ações Prioritárias para I4+
1. **Validar entrada** na API (min 3 chars, rejeitar whitespace-only)
2. **Corrigir case sensitivity** do setor (converter para lowercase no SQL)
3. **Adicionar ordenação por relevância** no retriever (score de match)
4. **Retornar briefing null** quando 0 startups
5. **Limitar keywords** a máximo 8
