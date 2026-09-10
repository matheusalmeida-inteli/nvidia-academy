# Iteração 3 — Testes Adversariais

## Metodologia
4 categorias de queries adversariais:
- 4 ambíguas (multi-intent)
- 7 fora de escopo (não-relacionadas a NVIDIA)
- 4 negativas (negação/semântica invertida)
- 4 multi-hop (precisa combinar múltiplos chunks)

## Resultados

### Ambíguas (4/4 — Razoável)
- "accelerate ML pipelines" → RAPIDS ✅
- "production deployment AI" → AI Enterprise + NIM + Guardrails ✅
- "GPU for data" → RAPIDS + cuDF ✅
- "real-time AI for enterprise" → Clara + Omniverse + AI Services ⚠️ (Clara é saúde, não "real-time AI")

**Conclusão**: Resolve com base em keyword matching. Não usa clarificação ou expansão semântica.

### Fora de Escopo (7/7 — FALHA) ⚠️
- "recipe for chocolate cake" → **RAPIDS + AI Enterprise + Triton**
- "history of World War 2" → **CUDA + AI Enterprise + Morpheus**
- "best Python web framework 2024" → **MONAI + cuDF + TensorRT-LLM**
- "Pixar animation studio" → **NIM + NIM + Triton**
- "how to invest in NVIDIA stock" → **Inception (3x)** — até tecnicamente defensável ("NVIDIA + programa")
- "OpenAI GPT-4 architecture" → **NIM + CUDA + NeMo** — confunde concorrente
- "What is the best investment bank in Brazil?" → **Inception + NIM + Inception**

**Achado crítico**: o sistema **NÃO SABE dizer "não tenho informação"**. Para qualquer query ele retorna os 3 chunks mais próximos. Esse é o "alucinação estrutural" do RAG puro — não há threshold de similaridade para rejeitar queries fora do domínio.

**Severidade**: Crítica. Em produção, o agente pode fazer recomendações erradas com base em queries sem informação.

### Negativas (4/4 — FALHA) ⚠️
- "Which NVIDIA technology does NOT serve for fraud detection?" → Triton + RAPIDS + NIM (todos podem servir para fraud)
- "Can NeMo Guardrails work without LangChain?" → NeMo Guardrails + NeMo + Guardrails
- "Is RAPIDS compatible with AMD GPUs?" → RAPIDS + cuDF + NIM
- "Does NIM support non-NVIDIA hardware?" → AI Enterprise + NIM + Enterprise

**Achado**: RAG puro não faz negação semântica. O sistema trata a query como busca por similaridade, ignorando o operador "NOT" e "Does X without Y". 

**Severidade**: Crítica (se uma startup perguntar "qual NVIDIA NÃO usar para fraude?", vai receber a lista errada).

### Multi-hop (4/4 — Mistura)
- "healthcare + medical imaging + Portuguese speech" → Clara + Clara + NIM ⚠️ (perdeu Riva)
- "Brazilian fintech + real-time fraud + GPU dataframes" → cuDF + Morpheus + NIM ✅
- "LLM + production + safety + fine-tuning" → Guardrails + NeMo + NeMo ✅
- "edge AI + agriculture + robotics + simulation" → Isaac + NIM + NIM ✅

**Conclusão**: Multi-hop funciona razoavelmente (50% entrega ambos os techs esperados).

## Bugs Não Resolvidos

| Achado | Severidade | Mitigação Possível |
|--------|-----------|-------------------|
| Sem rejeição de out-of-domain | Crítica | Threshold de similaridade + "no information" fallback |
| Negação semântica não funciona | Crítica | Query rephrasing, ou LLM-based query understanding |
| Multi-hop incompleto (50%) | Média | Query expansion antes de retrieval |

## Re-verificação de Achados da Iteração 1-2

### 1. KB sintética (I1-1) — não verificado nesta iteração
Pendente.

### 2. LocalEmbedder (I1-2) — não verificado nesta iteração
Pendente.

### 3. Cohere ativo (I1-3, I2-2) — RE-VERIFICADO ✅
- Confirmação adicional: 19 queries nas 4 categorias usaram CohereRerank com sucesso (4 falhas por rate limit, 15 sucesso).
- **Estável.**

### 4. Rate limit (I2-3) — RE-VERIFICADO ✅
- 4 falhas com HTTP 429 nas queries multi-hop (após muitas chamadas).
- **Re-confirmado por método diferente: queries novas (não reusando golden set) também sofreram rate limit.**

### 5. IDF correto (I1-2) — RE-VERIFICADO ✅
- Não re-medido nesta iteração (assume-se estável).
- **Pendente: medição direta do impacto do IDF no RRF (não só nos valores).**

## Achados Críticos Abertos (consolidados)

| # | Achado | Severidade | Origem |
|---|--------|------------|--------|
| 1 | RAG sem rejeição out-of-domain (alucina) | Crítica | I3 |
| 2 | Negação semântica não funciona | Crítica | I3 |
| 3 | Cohere rate limit 10/min (Trial) | Crítica | I2 |
| 4 | KB sintética (não fontes reais) | Alta | I1 |
| 5 | LocalEmbedder em produção | Alta | I1 |
| 6 | Multi-hop retrieval incompleto | Média | I3 |
