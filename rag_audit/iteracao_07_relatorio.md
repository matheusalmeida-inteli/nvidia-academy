# Iteração 7 — Cobertura por Qualidade + Re-verificação I5

## Metodologia
1. Para cada uma das 16 techs do TAPI §5.4, query direta e específica
2. Verificar: a tech aparece no top-3? Qual a posição?
3. Investigar falhas em detalhe

## Resultados: Cobertura por Qualidade

| Tech | Top-3? | Rank | Status |
|------|---------|------|--------|
| NVIDIA Inception | ✅ | 1 | Boa |
| NVIDIA NIM | ✅ | 1 | Boa |
| NVIDIA NeMo | ✅ | 1 | Boa |
| NeMo Guardrails | ✅ | 1 | Boa |
| Triton | ✅ | 1 | Boa |
| TensorRT-LLM | ✅ | 1 | Boa |
| RAPIDS | ✅ | 1 | Boa |
| cuDF | ✅ | 1 | Boa |
| cuML | ✅ | 1 | Boa |
| CUDA | ✅ | 1 | Boa |
| NVIDIA Riva | ✅ | 1 | Boa |
| NVIDIA Omniverse | ✅ | 1 | Boa |
| NVIDIA Isaac | ✅ | 3 | Fraca |
| NVIDIA Clara | ✅ | 1 | Boa |
| NVIDIA Morpheus | ❌ | - | **Fracasso** |
| AI Enterprise | ✅ | 1 | Boa |

**15/16 (94%) no top-3. 14/16 (87%) no top-1.**

## Achado 1: NVIDIA Morpheus falha em query direta ⚠️

**Causa raiz**: Dense retrieval retornou Clara como top-1 para query sobre Morpheus.

Investigação para query "What is NVIDIA Morpheus for cybersecurity?":
- Dense top-5: Clara (0.176), Clara (0.171), NeMo (0.153), Triton (0.147), Isaac (0.139) — **Morpheus NÃO aparece**
- BM25 top-5: Morpheus (12.6), Morpheus (11.0), Morpheus (6.8), Morpheus (5.3), Morpheus (4.9) — **Morpheus CORRETO**

**RRF fusion**: Clara 0.0679 vs Morpheus 0.0605 — Clara vence por margem fina (1.2x).

**Conclusão**: o sistema RRF com k=60 favorece o dense na margem. Morpheus tem só 6 chunks vs Clara 19 — o dense retrieval não consegue encontrar Morpheus semanticamente. A solução é RRF com peso maior para BM25 ou threshold mínimo de BM25 antes de RRF.

## Achado 2: NVIDIA Isaac rank=3 (fraco)

Para "What is NVIDIA Isaac for robotics simulation?":
- Top-1: NIM, Top-2: NeMo, Top-3: Isaac

Causa: similar à Morpheus — dense retrieval falha para "Isaac" mas BM25 é correto.

## Achado 3: Citações para techs de cobertura fraca

Verificação de fidelidade para Isaac (rank=3) e Morpheus (fail):
- Morpheus não foi recuperado, então não há citação a verificar
- Isaac rank=3: chunk citeado corretamente contém "Isaac"

**Re-verificação I5**: As citações são fiéis (o chunk citeado menciona Isaac). O problema está no retrieval, não na citação.

## Achado 4: Techs com baixa cobertura de chunks e retrieval fraco

| Tech | Chunks na KB | Retrieval Dense | Retrieval BM25 | RRF |
|------|-------------|----------------|---------------|-----|
| Morpheus | 6 | ❌ (0.0) | ✅ (alta) | ❌ |
| Isaac | 7 | ❌ (0.0) | ✅ (alta) | ❌ |
| Clara | 6 | ✅ (dominante) | ✅ (alta) | ✅ |

**Padrão**: techs com chunks curtos e poucos exemplos → dense retrieval falha → RRF é corrompido pelo dense.

## Re-verificação I5: Citações (re-check)

Para Morpheus (não recuperado) e Isaac (rank=3):
- Morpheus: sem citação (nenhum chunk recuperado)
- Isaac rank=3: citação fiel ao chunk ✅

**Hipótese testada e REPROVADA**: "a fidelidade de citação é pior para techs com menos chunks". Na verdade, techs com poucos chunks sofrem mais no **retrieval** (não na citação).

## Correção Proposta

**Não corrigida nesta iteração** — requer decisão sobre:
1. Aumentar peso de BM25 no RRF (reduzir k de 60 para 30-40)
2. Adicionar threshold mínimo de BM25 antes de RRF
3. Usar scores de BM25 como gate para o dense (se BM25 tem score alto, o dense é desprezado)

## Achados em Aberto

| # | Achado | Severidade | Ação |
|---|--------|------------|------|
| I7-1 | Morpheus falha em query direta (dense fraco) | Alta | Reduzir peso dense no RRF |
| I7-2 | Isaac rank=3 (fraco) | Alta | Reduzir peso dense no RRF |
| I2-3 | Cohere rate limit 10/min | Crítica | Produzir chave ou fallback local |
| I3-1 | Out-of-domain sem rejeição | Crítica | Threshold de score |
| I1-1 | KB sintética | Alta | Ingestão de fontes reais |
