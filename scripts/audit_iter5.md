# Audit Iter 5 — Score de Fit e Breakdown

**Data:** 2026-08-29  
**Escopo:** Cálculo de inception_fit_score, fit_breakdown, moat_score

## Descobertas críticas (P0)

### 38. NENHUMA startup atinge fit_score >= 0.4 — todos os 31 retornos < 0.4
- **Causa:** `moat_score` colapsa para 0.0 em 100% dos casos (docs de vagas)
- **Composição:** fit = moat_s(0.30) + tech_s(0.20) + sector_s(0.20) + traction_s(0.15) + bonus(0.15)
- **Com moat=0:** fit máximo = 0.20 + 0.20 + 0.15 = 0.55 (com bonus). MAS isso requer tech_s=1.0 + sector_s=1.0 + traction_s=1.0
- **Real:** tech_s=0.0, sector_s=0.75, traction_s=0.0 → fit = 0.20 + 0.0 + 0.0 = 0.20 (com bonus=0.15 = 0.35)
- **Bonus nunca ativa** porque `moat >= 2.0` nunca é atingido

### 39. O breakdown é ILÓGICO — "tech" mostra 0.67 quando tech_score=0.0
- **Causa:** `breakdown["tech"] = tech_s / 0.20 = 0.67` — está normalizando contra weight, não contra o que foi computado
- **Lógica atual:** `tech_s` (range 0-1) ÷ `0.20` (weight) = 0-5 valor
- **Resultado:** Mostra valores 0-5 em vez de 0-1, confunde o usuário
- **Mesmo problema:** "moat" mostra 0.02 quando moat=0.0 (não devia ser 0.0?)

### 40. tech_score dá peso 0 para qualquer coisa que não seja "cuda/gpu/tensorrt/triton/tts/asr/rag"
- **Causa:** Lista hardcoded de NVIDIA keywords é restritiva
- **Impacto:** "pytorch", "tensorflow" são listados como `nvidia_stack` mas só dão 0.3 weight cada
- **Startup com "gpt-4" no stack** (que é compatível com NIM): tech_score=0

### 41. sector_score é binário (1 keyword match = 0.75, 0 = 0.4)
- **Causa:** `_sector_score` retorna primeiro match ou 0.4 default
- **Problema:** Não considera qualidade (saúde > manufatura > varejo é tratado igual)
- **Default 0.4 é muito alto** — "varejo" deveria ser pior que "robótica"

## Descobertas altas (P1)

### 42. Bonus de 0.15 nunca ativa
- **Condição:** `moat >= 2.0 and custom_model` — requer moat >= 2.0
- **Hoje:** moat=0 em 100% dos casos
- **Sem o bonus, fit max = 0.85** (sempre 0.15 short do 1.0)

### 43. `_traction_score` é baseado apenas em descricao_curta, não em documentos
- **Causa:** `desc = profile.get("descricao", "")` — descrição resumida, não os docs
- **Resultado:** Nunca vê "1000+ clientes" nos docs de vagas (estão em descricao_curta, mas é só 200 chars)

### 44. fit_breakdown inconsistente com o fit_score
- `Liqi: {'moat': 0.02, 'tech': 0.67, 'sector': 0.75, 'traction': 0.2}` — soma 1.64, mas o fit é 0.32
- **Bug:** O breakdown usa "tech=0.67" mas o que contribuiu foi `0.67 * 0.20 = 0.134`
- **Display:** Deveria mostrar contribuição absoluta, não normalizada

## Descobertas médias (P2)

### 45. Moat_score pode ficar negativo no cálculo intermediário
- `_compute_moat` aplica penalidades mas retorna `max(0.0, ...)` — ok
- Mas scores intermediários (sem `max`) podem causar confusão se a função for chamada separadamente

### 46. Não há threshold para "rejeitar" startup (fit < X)
- Sistema não diz "essa startup NÃO deve entrar no Inception"
- Tudo é apresentado como "baixo fit" mas segue em frente

## Ações para I6+
1. **Mudar breakdown para mostrar 0-1 valores** consistentes
2. **Adicionar proporcionalidade nos pesos** (não mais 0.30 + 0.20 + 0.20 + 0.15 = 0.85 com bonus = 1.0)
3. **Repensar tech_score** para ser mais inclusivo (qualquer LLM framework conta)
4. **Refazer extractor** para capturar moat de docs de produto (não vagas)
5. **Adicionar minimum thresholds** para cada componente
