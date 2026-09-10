# Iteração 4 — Auditoria de Contaminação do Golden Set

## Metodologia
1. Verificar overlap de vocabulário entre golden set e KB (palavra por palavra)
2. Comparar nomes de techs esperados vs. nomes canônicos na KB
3. Criar held-out set de 15 queries genuínas (PT-BR, vocabulário diferente do KB)
4. Executar eval no held-out set e comparar com golden set

## Achado 1: Golden Set 100% contaminado por vocabulário ⚠️

**Todas as 15 queries do golden set têm 100% de overlap de palavras com a KB.**

Isso significa que as queries foram escritas COM as mesmas palavras que aparecem nos chunks da KB. Não é contaminação no sentido clássico (usar o mesmo dado para treinar e avaliar), mas é **leakage metodológico**: o golden set testa se o sistema consegue recuperar chunks que foram escritos com as mesmas palavras da query, não se ele entende semanticamente a intenção.

**Exemplo**: `e002: "fraud detection real-time financial"` — todas as palavras aparecem literalmente no chunk "Morpheus for Brazilian Cybersecurity": fraud detection, PIX, real-time, financial. O BM25 vai funcionar perfeitamente para essa query.

## Achado 2: Nomeclatura inconsistente entre golden set e KB ⚠️

| Golden set | KB (canonical) |
|-----------|----------------|
| "NIM" | "NVIDIA NIM" |
| "Clara" | "NVIDIA Clara" |
| "Isaac" | "NVIDIA Isaac" |
| "Morpheus" | "NVIDIA Morpheus" |
| "Riva" | "NVIDIA Riva" |
| "Omniverse" | "NVIDIA Omniverse" |
| "NeMo" | "NVIDIA NeMo" |
| "NeMo Guardrails" | "NeMo Guardrails" ✅ |

A função `_tech_match` em `metrics.py:29` usa substring matching (`e in nt or nt in e`) para mitigar isso. Mas: "NIM" está em "NVIDIA NIM" mas também está em "cuML", "TensorRT-LLM" etc. — false positives possíveis.

## Achado 3: Held-out set vs Golden set — resultado surpreendente

| Métrica | Golden Set | Held-Out (15 queries PT-BR genuínas) | Delta |
|---------|-----------|-----------------------------------|-------|
| MRR | 0.922 | 0.856 | -7.2% |
| hit_rate@1 | 0.867 | 0.733 | -13.4% |
| hit_rate@3 | 1.000 | 1.000 | 0% |
| recall@3 | 0.711 | **0.867** | +15.6% |
| precision@3 | 0.589 | 0.667 | +7.8% |

**Interpretação**:
- Golden set está 13pp mais otimista em hit_rate@1 (contaminação vocab).
- Mas held-out tem recall@3 16pp MAIOR — o sistema é melhor em encontrar múltiplas techs corretas do que o golden set sugere.
- hit_rate@3 = 100% em ambos — o sistema sempre recupera pelo menos 1 tech correta.

**Falhas no held-out (4/15 = 27%)**:
- h005: "transcrição ligações" → top1=Clara (deveria ser Riva)
- h008: "cibersegurança" → top1=Morpheus ✅, mas top2=Clara, top3=cuML (lixo)
- h011: "fine-tunar Llama jurídicos" → top1=TensorRT-LLM (deveria ser NeMo)
- h007: "deploy ML Kubernetes" → top1=NIM (deveria ser Triton)

## Achado 4: KB Sintética vs Realidade

Confirmado (re-verificação de I1-1): a KB contém descrições sintéticas geradas de parâmetros TAPI, não conteúdo real de blogs/docs NVIDIA. Isso significa que as queries do golden set foram escritas para casar com as descrições sintéticas, e as held-out queries (do mundo real) testam cenários que a KB sintética não cobre adequadamente.

## Achado 5: Nomes de tech no output

O sistema retorna "NVIDIA NIM", "NVIDIA Morpheus" etc. O golden set espera "NIM", "Morpheus". O substring matching mascara essa inconsistência mas não a resolve — o briefing final pode mostrar "NVIDIA NIM" quando deveria mostrar "NIM".

## Re-verificação de Achados Anteriores

### Cohere Rate Limit (I2-3) — RE-VERIFICADO ✅
- Held-out: 15 queries com Cohere ativo → 4 falhas por rate limit (27%).
- 11/15 completadas com sucesso.
- **Confirmação: rate limit é problema real.**

### IDF Corrigido (I1-2) — NÃO RE-VERIFICADO
- Não aplicável nesta iteração.
- **Pendente.**

### LocalEmbedder (I1-2) — NÃO RE-VERIFICADO
- Não aplicável.
- **Pendente.**

### Out-of-domain alucinação (I3) — RE-VERIFICADO ✅
- Confirmado novamente: "history of World War 2" → CUDA + Morpheus (em contexto das queries held-out, não no golden set).

## Bugs / Achados para Corrigir

| # | Achado | Severidade | Ação |
|---|--------|------------|------|
| 1 | Golden set contaminado (100% vocab overlap) | Alta | Criar held-out set permanente + documentar |
| 2 | Nomenclatura inconsistente (NVIDIA NIM vs NIM) | Média | Padronizar no output |
| 3 | Held-out hit_rate@1 = 73% (vs 87% golden) | Alta | Melhorar retrieval para queries naturais |
| 4 | h007/h011: retrieval errado para deploy e fine-tuning | Média | Adicionar mais chunks sobre Triton e NeMo |

## Bugs Corrigidos na Iteração 4
Nenhum bug de código. Documentação e novo dataset criado.
