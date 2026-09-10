# Audit Iter 1 — Mapeamento de bugs latentes

**Data:** 2026-08-29  
**Escopo:** Auditoria estática do código + execução de 10 cenários de teste

## Descobertas críticas (P0)

### 1. Dataset de documentos é "vagas de emprego" — bloqueia toda a análise de moat
- **Causa:** Os 208 documentos sintéticos gerados por `scraper/synthesize_docs` são descrições de vagas de emprego (ex: "Vaga: AI Engineer — Nubank", "Tech Lead — Liqi"), não conteúdo de produto/empresa.
- **Impacto:** Para TODAS as 52 startups, o extractor não consegue identificar moat (proprietary_data, custom_model, workflow_depth ficam vazios) — todos os scores de moat colapsam para 0.1
- **Evidência:** Nubank ("usa ML extensivamente para crédito, fraude, atendimento e personalização") retornou `sinais_ai=[]`, `proprietary_data=[]`, `custom_model=[]`. Bagunça o motor inteiro.
- **Exemplo de trecho de documento:** "Vaga: AI Engineer — Nubank. Sobre a Nubank: Banco digital — usa ML extensivamente..."

### 2. Cobertura de keywords AI_SIGNALS é drasticamente insuficiente
- **Causa:** Lista `AI_SIGNALS` tem "machine learning" mas não "ml", "ia", "ai", "inteligência artificial", "modelo de" — todos aparecem nos docs sintéticos
- **Impacto:** Nubank, Dasa (classificadas como ai_native no banco) são processadas como "non_ai" pelo extrator
- **Caso Liqi:** "plataforma com machine learning" → 1 match. "Banco digital — usa ML" → 0 matches.

### 3. Retriever retorna 0 startups em 3 de 10 cenários
- **Cenários vazios:** A6_retail, A7_robotics, A8_cybersec
- **Causa:** Setores (Varejo, Robótica, Cybersecurity) não existem nos dados de 52 startups sintéticas. Mas isso é parcialmente válido (não há startups sintéticas nesses setores). O briefing fica com empresa="?" porque pega a primeira.
- **Comportamento errado:** quando `startups=[]`, o briefing usa a primeira empresa do estado vazio (None), gera briefing sem nome.

### 4. Briefing aparece mesmo com 0 startups relevantes
- **Causa:** O `nó briefing` sempre gera um briefing pegando a primeira startup do state, mesmo que essa startup não seja relevante para a query
- **Exemplo:** A1_fintech_native → briefing = Liqi (a startup com moat mais baixo, não a mais relevante). Não há signal de "qual briefing é para qual startup".

## Descobertas altas (P1)

### 5. Recomendações são 100% template, sem personalização
- **Causa:** `recommend_for()` ignora `gaps_identificados` na geração das justificativas; usa o mesmo texto para todo mundo
- **Exemplo:** "Pesquisar X no portal NVIDIA e entrar em contato com Inception" é idêntico para todas as startups e todas as tecnologias
- **Impacto:** Mostra "cumprimento artificial" do TAPI: gera saída estruturada, mas sem verdade contextual

### 6. Community actions ignoram moat/wrapper
- **Causa:** `community_actions_for()` tem bloco para wrapper_llm, mas aparece em todas as startups com `categoria=wrapper_llm` independentemente do tipo de nutrição necessária
- **Bugs:** "Peer intro com outra fintech do portfolio Inception Brasil" para Liqi (wrapper) — não faz sentido, pois Liqi não é AI-native

### 7. Inception fit score com quebra estrutural
- **Causa:** `_inception_fit_score` divide moat por 5 (max 1.0), mas `_compute_moat` retorna 0-5 também. Quando moat=0.1, moat_s = 0.006. Soma com sector_s (0.75 max) = 0.756 máximo quando moat=0.1
- **Resultado:** Fit score nunca é alto se o extractor não pega moat — o que é o caso para todas as 52 startups sintéticas

## Descobertas médias (P2)

### 8. Sinais de IA no text NÃO são case-insensitive para descrição inteira
- `native_score += sum(1 for s in AI_NATIVE_SIGNALS if s in desc)` — usa lowercase já, ok. Mas não cobre formas variantes ("IA" vs "inteligência artificial", "ML" vs "machine learning")

### 9. `_traction_score` é muito restritivo
- Só pontua com "1000+", "10k+", "100k+", mas docs sintéticos não mencionam números

### 10. RAG retrieval top_k=2 e limit de 5 techs é muito restritivo
- `seen_techs` é deduplicado por tech mas max 5 — pode cortar techs relevantes

## Pontos a investigar nas próximas iterações
- **I2:** Verificar se a pipeline REALMENTE está apenas cumprindo o formato TAPI sem substância (recomendações genéricas, justificativas copiadas)
- **I3:** Casos onde o sistema falha silenciosamente (startup não existe, RAG sem resultados, score zerado)
- **I4:** Onde estão as fontes / evidências? O usuário recebe justificativa sem rastro de auditoria
- **I5:** Validar o cálculo de fit_breakdown e inception_fit_score com casos conhecidos
- **I6:** Verificar se as top 6 recomendações são realmente as melhores ou se são "default"
- **I7:** Ações técnicas vs comerciais: diferenciação real ou placeholders?
- **I8:** Anti-wrapper está consistente? Validar manualmente
- **I9:** Performance, latência, custo de chamadas
- **I10:** UI edge cases (estados vazios, loading, erro)

## Plano de correção P0
1. **Regenerar dataset sintético** com descrições reais de produto, não vagas
2. **Ampliar AI_SIGNALS** para cobrir abreviações
3. **Não gerar briefing** quando `startups=[]`
4. **Adicionar campo `categoria` no briefing** para saber qual startup é o alvo
5. **Recomendações devem citar o gap específico** da startup, não template

## Status
- 10 cenários executados: 7 retornaram startups, 3 retornaram 0
- Briefing sempre gerado, mesmo em 0 startups
- Todas as startups com moat < 1.0 (Nubank 0.1, Dasa 0.1) — bug estrutural
- Recomendações idênticas em todas as startups — bug grave de "fake compliance"
