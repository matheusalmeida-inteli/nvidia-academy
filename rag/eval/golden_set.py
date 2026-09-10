"""Golden evaluation set — (query, expected_techs, context) tuples.

Each sample covers a real-world scenario from the TAPI §5.5 recommendation logic.
Used by rag/eval/run_eval.py to compute retrieval metrics.
"""
from __future__ import annotations

EVAL_SAMPLES: list[dict] = [
    {
        "id": "e001",
        "query": "optimize LLM inference production latency",
        "techs_esperadas": ["NVIDIA NIM", "TensorRT-LLM", "Triton"],
        "contexto": "Startup usa LLMs para chatbots mas sofre com latência e custo de API externa.",
    },
    {
        "id": "e002",
        "query": "fraud detection real-time financial",
        "techs_esperadas": ["cuML", "Morpheus", "RAPIDS"],
        "contexto": "Fintech processando milhões de transações/dia precisa detectar fraude em tempo real.",
    },
    {
        "id": "e003",
        "query": "speech recognition Portuguese Brazil voice",
        "techs_esperadas": ["Riva", "NVIDIA NIM"],
        "contexto": "Startup de call center precisa de transcrição e síntese de voz em português.",
    },
    {
        "id": "e004",
        "query": "medical imaging AI healthcare diagnosis",
        "techs_esperadas": ["Clara", "MONAI", "NIM"],
        "contexto": "Healthtech analisando exames de imagem com modelos de deep learning.",
    },
    {
        "id": "e005",
        "query": "GPU accelerated data science large dataset",
        "techs_esperadas": ["RAPIDS", "cuDF", "cuML"],
        "contexto": "Startup processando terabytes de dados tabulares com pandas/sklearn lento.",
    },
    {
        "id": "e006",
        "query": "robotics simulation autonomous machine",
        "techs_esperadas": ["Isaac", "Omniverse"],
        "contexto": "Startup de robótica industrial precisa simular e fazer deploy em edge.",
    },
    {
        "id": "e007",
        "query": "startup program benefits GPU credits NVIDIA",
        "techs_esperadas": ["NVIDIA Inception"],
        "contexto": "Early-stage AI startup buscando benefícios, créditos e suporte NVIDIA.",
    },
    {
        "id": "e008",
        "query": "AI agent safety guardrails enterprise",
        "techs_esperadas": ["NeMo Guardrails", "NeMo"],
        "contexto": "Empresa construindo agentes de IA e precisa de governança e controle de comportamento.",
    },
    {
        "id": "e009",
        "query": "digital twin factory simulation 3D",
        "techs_esperadas": ["Omniverse"],
        "contexto": "Manufatura construindo réplicas digitais de fábricas para otimização.",
    },
    {
        "id": "e010",
        "query": "LLM fine-tuning customization proprietary data",
        "techs_esperadas": ["NeMo", "NVIDIA NIM"],
        "contexto": "Startup quer customizar LLM com dados proprietários usando fine-tuning e RLHF.",
    },
    {
        "id": "e011",
        "query": "cybersecurity threat detection anomaly SOC",
        "techs_esperadas": ["Morpheus", "RAPIDS"],
        "contexto": "Empresa de cibersegurança processando logs de rede para detectar ameaças.",
    },
    {
        "id": "e012",
        "query": "agriculture precision farming AI",
        "techs_esperadas": ["RAPIDS", "cuML", "Isaac", "cuDF"],
        "contexto": "AgTech processando dados de sensores de campo para decisões de plantio.",
    },
    {
        "id": "e013",
        "query": "model serving production kubernetes",
        "techs_esperadas": ["Triton", "AI Enterprise"],
        "contexto": "Startup fazendo deploy de múltiplos modelos em produção com Kubernetes.",
    },
    {
        "id": "e014",
        "query": "CUDA programming custom kernel optimization",
        "techs_esperadas": ["CUDA"],
        "contexto": "Time técnico quer escrever kernels CUDA customizados para operações de ML.",
    },
    {
        "id": "e015",
        "query": "generative AI video image synthesis",
        "techs_esperadas": ["NVIDIA NIM", "Omniverse"],
        "contexto": "Startup gerando imagens e vídeos sintéticos para marketing e e-commerce.",
    },
    # === Portuguese-language samples (TAPI requires Brazilian context) ===
    {
        "id": "p001",
        "query": "startup de saúde com modelos de imagem médica",
        "techs_esperadas": ["Clara", "MONAI", "NIM"],
        "contexto": "Healthtech brasileira analisando exames de imagem com deep learning.",
    },
    {
        "id": "p002",
        "query": "fintech com detecção de fraude em tempo real",
        "techs_esperadas": ["Morpheus", "RAPIDS", "cuML", "NIM"],
        "contexto": "Fintech processando milhões de transações e precisa detectar fraude.",
    },
    {
        "id": "p003",
        "query": "call center com voz e transcrição em português",
        "techs_esperadas": ["Riva", "NIM"],
        "contexto": "Startup de call center precisa de ASR e TTS em português brasileiro.",
    },
    {
        "id": "p004",
        "query": "startup de agronegócio com dados de sensores e satélite",
        "techs_esperadas": ["RAPIDS", "cuML", "Isaac", "cuDF"],
        "contexto": "AgTech processando terabytes de dados de campo para agricultura de precisão.",
    },
    {
        "id": "p005",
        "query": "startup de robótica com simulação de robôs",
        "techs_esperadas": ["Isaac", "Omniverse"],
        "contexto": "Startup industrial simulando robôs antes do deploy em fábrica.",
    },
    {
        "id": "p006",
        "query": "como servir modelos de aprendizado de máquina em produção",
        "techs_esperadas": ["Triton", "NIM", "AI Enterprise"],
        "contexto": "Startup fazendo deploy de múltiplos modelos com Kubernetes.",
    },
    {
        "id": "p007",
        "query": "agentes de IA com governança e segurança",
        "techs_esperadas": ["NeMo Guardrails", "NeMo"],
        "contexto": "Empresa construindo agentes e precisa controlar comportamento com guardrails.",
    },
    {
        "id": "p008",
        "query": "startup quer customizar modelo de linguagem com dados próprios",
        "techs_esperadas": ["NeMo", "NIM"],
        "contexto": "Fine-tuning de LLM com dados proprietários usando RLHF.",
    },
    {
        "id": "p009",
        "query": "processamento de grandes volumes de dados tabulares",
        "techs_esperadas": ["RAPIDS", "cuDF", "cuML"],
        "contexto": "Startup processando datasets grandes com pandas/sklearn lento em CPU.",
    },
    {
        "id": "p010",
        "query": "cibersegurança detecção de ameaças em tempo real",
        "techs_esperadas": ["Morpheus", "RAPIDS"],
        "contexto": "Empresa de segurança analisando logs de rede para detectar ameaças.",
    },
    {
        "id": "p011",
        "query": "benefícios do programa NVIDIA para startups em estágio inicial",
        "techs_esperadas": ["NVIDIA Inception"],
        "contexto": "Startup early-stage buscando créditos GPU e suporte NVIDIA.",
    },
    {
        "id": "p012",
        "query": "otimizar custo e latência de inferência de LLM em produção",
        "techs_esperadas": ["NIM", "TensorRT-LLM", "Triton"],
        "contexto": "Startup usando APIs externas quer reduzir custo de inferência.",
    },
    # === Ambiguous / multi-tech queries ===
    {
        "id": "a001",
        "query": "como servir modelos de forma escalável",
        "techs_esperadas": ["Triton", "NIM", "AI Enterprise"],
        "contexto": "Query ambígua que deve mapear para serving/MLOps.",
    },
    {
        "id": "a002",
        "query": "stack para aplicações de IA generativa",
        "techs_esperadas": ["NIM", "NeMo", "TensorRT-LLM"],
        "contexto": "Stack completo para gerar e servir conteúdo generativo.",
    },
    {
        "id": "a003",
        "query": "acelerar ciência de dados com GPU",
        "techs_esperadas": ["RAPIDS", "cuDF", "cuML", "CUDA"],
        "contexto": "Startup quer acelerar análise de dados e ML com GPU.",
    },
    {
        "id": "a004",
        "query": "saúde e inteligência artificial diagnósticos",
        "techs_esperadas": ["Clara", "MONAI", "NIM"],
        "contexto": "Equipe de saúde usando IA para diagnósticos.",
    },
    {
        "id": "a005",
        "query": "otimização de LLM para redução de custo",
        "techs_esperadas": ["TensorRT-LLM", "NIM", "Triton"],
        "contexto": "Startup quer reduzir custo por token de inferência de LLM.",
    },
    {
        "id": "a006",
        "query": "nvidia inception o que é e benefícios",
        "techs_esperadas": ["NVIDIA Inception", "NIM", "NeMo"],
        "contexto": "Startup pesquisando programa NVIDIA Inception e tecnologias associadas.",
    },
]
