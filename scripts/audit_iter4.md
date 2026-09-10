# Audit Iter 4 — Evidências e Citações

**Data:** 2026-08-29  
**Escopo:** Fontes, evidências, citations, rastreabilidade das recomendações

## Descobertas críticas (P0)

### 28. Nenhuma citação NVIDIA KB nas recomendações — todas são TECH_DEFS estáticos
- **Causa:** `recommend_for` lê `references` (do RAG) mas só usa `r["score"]` para filtering. As justificativas de TECH_DEFS são usadas para TODAS as startups
- **Resultado:** "CUDA: Programação paralela em GPU para kernels customizados" é a mesma justificativa para Nubank (fintech), Dasa (saúde), Loggi (logística)
- **Nenhuma startup vê justificativa diferente** — não há PERSONALIZAÇÃO

### 29. Techs duplicadas no output (NVIDIA Morpheus vs Morpheus)
- **Causa:** RAG retorna "NVIDIA Morpheus" E o `TECH_MAPPING` também gera "Morpheus" — ambos passam o deduplicate `seen_techs`
- **Resultado:** UI mostra duas techs com justificativas quase idênticas
- **Exemplo real:** Nubank recebe "Morpheus" e "NVIDIA Morpheus" como techs separadas

### 30. NVIDIA Clara recomendada para fintech (sem sentido setorial)
- **Causa:** `SECTOR_TECH` adiciona "Clara" para `fintech`? Não. O RAG retorna Clara baseado em similaridade de texto (job posting menciona "saúde"? Não). O deduplicate de `nvidia_rag` usa `seen_techs` por `tech` mas não filtra por setor
- **Resultado:** Briefing recomenda Clara para Nubank — completamente irrelevante

### 31. Recomendações sem rastreabilidade para o usuário
- **Causa:** `evidencias` no `recommend_for` é `[f"Gap: {g}" for g in gaps[:2]]` — não cita URLs, não referencia o chunk específico do RAG
- **Dado:** Briefing mostra `fontes_consultadas` = URLs das fontes dos documentos (vagas, neofeed), não da NVIDIA KB
- **Problema:** O usuário não consegue AUDITAR de onde veio cada recomendação

## Descobertas altas (P1)

### 32. `proxima_acao` é idêntica para todas as techs
- **Todas:** "Pesquisar X no portal NVIDIA e entrar em contato com Inception"
- **Correção:** Diferenciar por tech e contexto (e.g., CUDA → "Verificar programa CUDA Developer Program", NIM → "Solicitar acesso early access NIM")

### 33. `justificativa_negocio` também é estática
- Mesmo para "NVIDIA AI Enterprise": "Facilita procurement em clientes enterprise"
- Para fintech (Nubank), isso faz sentido. Para uma health startup, não

### 34. Briefing fontes não distingue documento vs NVIDIA KB
- `fontes_consultadas` mistura URLs de vagas + URLs do neofeed
- NVIDIA KB (RAG) URLs nunca são expostas ao usuário

### 35. Evidence validator não influencia recomendações
- `evidence_results` é gerado mas NUNCA é usado em `recommend_for`
- Só `lacunas` aparece no briefing como texto genérico

## Descobertas médias (P2)

### 36. `evidence_score` é trivial (0.5 × docs + 0.4 × signals + 0.1)
- Qualquer startup com 1 documento + 1 sinal AI já tem score > 0.5
- Não valida QUALIDADE das evidências

### 37. Campo `evidencias` nas Recs é sempre vazio para 95% das startups
- Porque `gaps_identificados` é raramente preenchido pelos docs de vagas
- Quando preenchido, é sempre "No GPU optimization in current stack" — genérico

## Ações Prioritárias para I5+
1. **Adicionar sector filter** em `recommend_for`: se tech não faz sentido para setor, remover ou rebaixa
2. **Remover techs duplicadas** (deduplicação por nome canônico, ex: "Morpheus" = "NVIDIA Morpheus")
3. **Usar o conteúdo do RAG** como justificativa real (citations)
4. **Separar fontes de docs vs NVIDIA KB** no briefing
5. **Deduplicar `references` de nvidia_rag** antes de passar para recommend_for
6. **Gerar ações específicas por tech** (não "Pesquisar X no portal")
