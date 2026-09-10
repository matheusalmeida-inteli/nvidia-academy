# Audit Iters 7–10 — Consolidado

## Iter 7 — Ações Técnicas e Comunitárias

**Descoberta 57: Ações comerciais são COPIAS idênticas em 6/10 cenários**
- "Agendar reunião de descoberta com foco em NVIDIA NIM" aparece 6x — sem variação
- Só muda quando `fit < 0.4` (troca para "Adiar abordagem")

**Descoberta 58: Community actions não verificam AI-native**
- Wrappers (Liqi, Stone, Nagro) recebem "Peer intro com outra fintech" e "NVIDIA Fintech Day"
- Faz sentido para fintech AI-native, não para wrappers que precisam de educação

**Descoberta 59: Ação "POC técnica com NIM" é sempre gerada**
- Se há `high_recs`, SEMPRE propõe NIM — sem checar se a startup realmente usa LLM

**Descoberta 60: Nenhuma ação é baseada no FIT BREAKDOWN**
- Se moat=0 (baixa defensibilidade), não há ação diferenciada
- Se sector=science (saúde), as ações comerciais deveriam ser diferentes

---

## Iter 8 — Anti-Wrapper Consistency

**Descoberta 61: Todos os wrappers têm moat=0.1**
- Não existe variação — todos colapsam no mesmo score
- Não há gradação (wrapper forte vs wrapper fraco)

**Descoberta 62: "ai_native" vs "wrapper_llm" são mutuamente exclusivos**
- Uma startup não pode ser ambas
- Mas existem startups que são "parcialmente wrappers" — uso de APIs + modelo próprio

**Descoberta 63: Wrappers deveriam ter ações de EDUCAÇÃO, não de INCEPTION**
- Sistema recomenda Inception para wrappers — contradiz TAPI §3
- community_actions_for() com `categoria == "wrapper_llm"` adiciona "Workshop defensibilidade"
- MAS ainda adiciona ações de "Convidar para GTC" e "Inception Capital Connect"

---

## Iter 9 — Performance

**Descoberta 64: Performance é BOA (0.1-0.5s)**
- fintech: 0.46s | saúde: 0.17s | logística: 0.13s
- Não há problema de performance

**Descoberta 65: DatabaseLoader pode vazar conexões**
- `DatabaseLoader` é context manager mas não há garantias de cleanup em caso de erro
- Multiplas chamadas ao DB por startup (1 para extractor, 1 para evidence)

**Descoberta 66: RAG retrieval é sequencial por startup**
- `for profile in profiles: queries = build_rag_queries(profile)` — não paralelo
- Para 8 startups × 3 queries = 24 retrievals sequenciais

---

## Iter 10 — UI Edge Cases

**Descoberta 67: Briefing com 0 startups gera "N/A" sem contexto**
- `/nurture` e `/pipeline` funcionam corretamente
- Página principal mostra loading state mas não há error state claro

**Descoberta 68: `evidencias_count` no StartupCard é o count de docs, não de evidências verificadas**
- Mostra "4 evidências" quando são 4 DOCUMENTOS
- Usuário pensa que são 4 evidências de moat

---

# PRIORIZAÇÃO FINAL DE CORREÇÕES

## P0 (Bloqueiam utilidade)
1. Query planner: validar entrada (min chars)
2. Briefing: não gerar quando 0 startups
3. Briefing: pick startup por maior fit, não [0]
4. Recomendações: deduplicar techs (canonical name)
5. Recomendações: setor-filter (Clara só health)
6. Justificativas: usar RAG content como evidência

## P1 (Qualidade)
7. AI_SIGNALS: adicionar "ml", "ia", "ai" como variantes
8. Community actions: separar educação vs engagement
9. Tech_DEFS: adicionar RAPIDS, AI Services, AI-Native Services
10. Fit breakdown: normalização consistente

## P2 (Nice-to-have)
11. BM25: alimentar com corpus NVIDIA KB completo
12. Paralelizar RAG retrieval por startup
13. DatabaseLoader: connection pooling mais robusto
