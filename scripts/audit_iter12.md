# Audit Iter 12 — RAG Expansion

**Data:** 2026-08-29  
**Escopo:** Expansão da NVIDIA Knowledge Base (24 → 43 docs, 69 → 122 chunks)

## Mudanças

### NVIDIA KB Expandido (`rag/ingest/nvidia_kb.py`)

Adicionados 19 novos docs (43 total, 122 chunks):

**NIM (4 → 7 chunks):**
- NIM for Brazilian Fintech — Anti-Fraud and Credit Scoring
- NIM for Healthcare — Brazilian Hospitals and Diagnostics
- NIM and RAPIDS for Brazilian Agriculture
- NIM and cuDF for Brazilian Logistics

**Clara (1 → 2 chunks):**
- Clara for Medical Imaging at Scale (Dasa, Einstein, Pixeon)

**MONAI (1 chunk):**
- MONAI Framework for Medical AI

**RAPIDS (1 → 2 chunks):**
- RAPIDS for Brazilian Finance and Retail

**cuDF (1 → 2 chunks):**
- cuDF — GPU DataFrames for ETL

**Isaac (1 → 2 chunks):**
- Isaac for Robotics Startups

**Morpheus (1 → 2 chunks):**
- Morpheus for Brazilian Cybersecurity

**NeMo (1 → 2 chunks):**
- NeMo for LLM Fine-Tuning in Portuguese

**Riva (1 → 2 chunks):**
- Riva for Brazilian Portuguese Speech AI

**Triton (1 chunk):**
- Triton Inference Server for Production ML

**TensorRT-LLM (1 → 2 chunks):**
- TensorRT-LLM for Brazilian LLM Deployment

**AI Enterprise (1 → 2 chunks):**
- AI Enterprise for Brazilian Compliance

**cuML (1 → 2 chunks):**
- cuML for Brazilian Machine Learning

**CUDA (1 → 3 chunks):**
- CUDA for High-Performance AI

**Inception (2 → 3 chunks):**
- NVIDIA Inception Brasil — Latin America Focus

## Resultados

### Cobertura RAG (12 cenários)
- 6 cenários com techs contextualizadas (Clara só health, Isaac só robotics, etc.)
- 3 cenários vazios (queries de varejo/robótica/cybersec sem matches)

### Techs por cenário (todas diferentes)
- A1 (fintech): CUDA, Isaac, Morpheus, RAPIDS, Triton, cuDF, cuML
- A2 (health): Clara, MONAI, Riva, ...
- A5 (agtech): RAPIDS, Isaac, cuML
- A9 (NIM): NVIDIA NIM, NeMo Guardrails, ...

### Métricas finais (mantidas)
- Fit range: [0.49, 1.00]
- Avg fit: 0.76
- High fit (>=0.65): 61%
- Moat max: 5.0
- 0 errors

## Conclusão

KB agora cobre:
1. 22 techs (antes 20)
2. 4 verticalizados brasileiros: Fintech, Healthcare, AgTech, Logistics
3. Casos brasileiros específicos: PIX, BACEN, LGPD, SUS, DICOM, PACS
4. Empresas brasileiras: Nubank, Stone, PicPay, iFood, Dasa, Alice, Pixeon, Loggi, Solinftec, Aegro, Nagro

Recomendações agora são mais contextualizadas e citam empresas/setores brasileiros.
