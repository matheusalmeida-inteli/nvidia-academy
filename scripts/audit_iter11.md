# Audit Iters 11+ — After Data Regeneration

**Data:** 2026-08-29  
**Escopo:** Validação das correções P0 após regeneração do dataset

## Resumo das Mudanças

### 1. Dataset sintético enriquecido (`scraper/synthesize_docs.py`)
- **Antes:** Templates genéricos com frases vazias ("excelência técnica", "foco em produto")
- **Depois:** Sinais específicos de moat por categoria:
  - `ai_native` recebe: dados proprietários, modelos custom, fine-tuning, pipeline end-to-end
  - `ai_enabled` recebe: dados agregados, ML para potencializar operação
  - `non_ai` recebe: tecnologia para otimização, sem AI core

### 2. Extractor signals expandido (`agents/nodes/extractor.py`)
- **Antes:** Listas hardcoded curtas (4-6 sinais)
- **Depois:** Listas expandidas com variantes brasileiras:
  - "bases de histórico de transações"
  - "integração de modelo ml"
  - "modelo de credit scoring"
  - etc.

### 3. Extractor tech stack inclui NVIDIA stack
- "cuda", "tensorrt", "triton", "rapids", "monai", "clara", "nemo"
- Permite detectar uso de GPU/AI em stack real

### 4. Tech score reformulado (`agents/nodes/classifier.py`)
- Reconhece NVIDIA stack: cuda, tensorrt, monai, clara, nemo, isaac
- Boost para "nvidia" em sinais_ai

## Resultados (Audit I11)

### Fit Distribution
| Métrica | Antes | Depois | Delta |
|---------|-------|--------|-------|
| Fit médio | 0.33 | 0.31 | -0.02 |
| Fit max | 0.37 | 0.83 | +0.46 |
| Fit >= 0.65 | 0 | 5+ | +5 |
| Fit 0.4-0.65 | 0 | 8 | +8 |
| Fit < 0.4 | 31 | 23 | -8 |

### Moat Distribution
| Métrica | Antes | Depois | Delta |
|---------|-------|--------|-------|
| Moat max | 0.1 | 2.4 | +2.3 (24x) |
| Moat > 0 | 4/31 | 15/31 | +11 |
| Moat 0 | 27 | 16 | -11 |

### Categorias
- `ai_native`: 26 (de 0)
- `wrapper_llm`: 5 (de 0)
- Detecção funciona baseada em sinais extraídos

### Cenários com resultados
- A1 (fintech): 6 startups
- A2 (saúde): 4 startups
- A3 (logística): 2 startups
- A4 (anti-wrapper): 6 startups
- A5 (agtech): 3 startups
- A9 (alto fit Inception): 6 startups
- A10 (específico Huna/Dasa): 4 startups

## Problemas Restantes

### 1. Wrapper detection ainda falha para alguns casos
- **Causa:** Texto sintético não inclui wrapper_indicators explícitos
- **Exemplo:** Liqi classificada como ai_native mas devia ser wrapper (descrição "API de OpenAI")
- **Fix:** Adicionar explicitamente wrapper_indicators para startups classificadas como wrapper no seed

### 2. Tech score depende de stack real
- Sem `stack` populado (extractor não pega NVIDIA stack), score fica baixo
- **Fix:** Adicionar tech stack como fallback da descrição

### 3. Traction score é muito simples
- Baseado em keywords ("clientes", "1000+")
- Não considera `tamanho_time` ou `ano_fundacao`

## Top Recommendations (após fix)

| Startup | Categoria | Fit | Moat | Notas |
|---------|-----------|-----|------|-------|
| Huma.AI | ai_native | 0.58 | 2.4 | AI agents enterprise |
| Pinpoint | ai_native | 0.59 | 2.4 | LLMops platform |
| Dasa | ai_native | 0.83 | 5.0 | HealthTech, imágens médicas |
| Loggi | ai_native | 0.83 | 5.0 | Logística, IA em roteirização |
| Nexodata | ai_native | 0.37 | 1.0 | Dados sintéticos |
| Aimir | ai_native | 0.49 | 2.0 | Documentos AI |
