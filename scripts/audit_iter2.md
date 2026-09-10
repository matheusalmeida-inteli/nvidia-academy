# Audit Iter 2 — Honestidade e Cumprimento Artificial

**Data:** 2026-08-29  
**Escopo:** Análise de personalização vs templates, faithfulness, signal-to-noise

## Descobertas críticas (P0)

### 11. Briefing ignora `user_query` — sempre usa `recommendations[0]`
- **Causa:** `build_briefing()` pega `recommendations[0]` sem considerar relevância para a query
- **Cenário A1_fintech_native:** Query pede "dados próprios" + "AI-native". Briefing = Liqi (wrapper_llm, moat=0.1) — exatamente o oposto
- **Cenário A4_wrapper_defense:** Query pede "defensibilidade real (não wrappers)". Briefing = Huma.AI (wrapper_llm, moat=0.1) — o pior caso possível
- **Impacto:** Briefing executivo vai para a startup que o usuário NÃO pediu

### 12. Recomendações idênticas para startups do mesmo setor
- **Cenário A2_health_imaging:** Alice, Dasa, Pixeon, Sami → todas retornam o mesmo set de 6 techs (CUDA, Morpheus, NVIDIA AI Enterprise, NVIDIA Clara, NVIDIA Morpheus, NVIDIA NIM) e as mesmas justificativas
- **Cenário A3_logistics:** Loggi, SuperFrete → idem
- **Causa:** `recommend_for()` usa apenas `text_all` (gaps + cases + sinais) para matching — quando todas têm sinais vazios, todas batem nas mesmas keywords genéricas
- **Consequência:** Lista de "top 6 techs" é na verdade um catálogo estático filtrado por setor, sem personalização

### 13. Tech "NVIDIA AI Enterprise" é sempre recomendada com justificativa placeholder
- **Causa:** Fallback no `recommend_for`: `("medium", "medium", f"Tecnologia NVIDIA para {tech}.", "Suporte NVIDIA para implementação.")`
- **Para "NVIDIA AI Enterprise"** especificamente, o `TECH_DEFS` define `("low", "low", "Plataforma enterprise com suporte SLA e compliance.", "Facilita procurement em clientes enterprise.")` — mas o fallback está sendo usado em vez do `TECH_DEFS` para techs novas

## Descobertas altas (P1)

### 14. RAG retrieval é subutilizado
- **`nvidia_rag` retorna até 5 techs únicas** por startup, mas depois `recommend_for` adiciona techs do mapeamento estático + sector
- **Resultado:** Recomendações finais são dominadas pelo mapeamento, não pelo RAG
- **Trace:** `nvidia_rag.build_rag_queries` ignora `gaps` se forem apenas 1 (não emite query) — baixa coverage

### 15. `query_planner` não emite constraints específicos
- **Impacto:** Todas as queries viram keywords genéricos — o RAG nunca recebe o contexto do "porque fintech" vs "porque logística"
- **Cenário A9_inception_fit:** Query "alto fit para Inception Brasil com NVIDIA NIM" — não vira constraint real, vira keywords no retriever

## Descobertas médias (P2)

### 16. Ações comerciais no briefing são placeholders textuais
- "Agendar reunião de descoberta com foco em NVIDIA NIM" — todas as startups com `high_recs` recebem isso
- Não há sinal se a startup está pronta para reunião ou se precisa primeiro entender NVIDIA
- Para wrappers, a ação "Conversa exploratória: ajudar a construir defensibilidade antes de pitch comercial" só aparece se `wrapper_warning=True` — mas mesmo assim é genérica

### 17. Community actions duplicam com as comerciais
- "Newsletter NVIDIA Inception" + "Convite para meetup" — fallback genérico quando nada bate
- "Peer intro com outra fintech" + "Convite para NVIDIA Fintech Day LATAM" — sempre para fintech, sem checar se a startup é mesmo AI-native (e.g., aparece para Liqi que é wrapper)

## Honestidade — pontos a atacar
1. **Recomendações devem citar GAPS específicos** da startup, não template global
2. **Briefing deve ser da startup mais relevante**, não a primeira
3. **Ordenar por score de relevância para a query** antes de pegar top
4. **Citations/evidências devem ser reais** (do RAG) e rastreáveis

## Ações para I3+
- Adicionar `relevance_score` por startup antes do briefing
- Trocar briefings para empresa com maior `relevance` × `fit`
- Refatorar `recommend_for` para que cada tech justifique-se com o gap da startup
- Adicionar campo `evidence_urls` por tecnologia recomendada
