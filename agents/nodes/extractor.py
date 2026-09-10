"""Agent 3: Extractor.

Extracts structured profile from unstructured document text:
- Stack técnico
- Casos de uso
- Gaps identificados
- Sinais de AI
- Moat signals (TAPI §1 anti-wrapper): proprietary data, workflow, custom model, distribution
- Categoria curada (via curated_seed lookup)
"""
from __future__ import annotations

import re

from loguru import logger

from agents.state import AgentState
from scraper.config.settings import get_settings
from scraper.curated_seed import ALL_STARTUPS
from scraper.pipelines.loaders import DatabaseLoader

_CURATED_CAT: dict[str, str] = {s["nome"]: s.get("categoria", "unknown") for s in ALL_STARTUPS}

AI_SIGNALS = {
    # LLM / foundation models
    "llm", "gpt", "llama", "mistral", "openai", "claude", "gemini", "langchain",
    "langgraph", "rag", "retrieval", "embedding", "vector db", "pinecone", "chroma",
    # NLP / conversational
    "nlp", "nlu", "computer vision", "ocr", "chatbot", "generative ai",
    "generativa", "generative", "machine learning", "deep learning", "neural", "transformer",
    "tensorflow", "pytorch", "sklearn", "hugging face", "diffusion", "stable diffusion",
    # Speech
    "tts", "asr", "voice", "speech",
    # GPU / inference stack
    "cuda", "gpu", "tensorrt", "triton", "nvidia",
    # NVIDIA health
    "clara", "monai", "medical imaging", "healthcare ai", "medical ai",
    # NVIDIA robotics / industrial
    "isaac", "jetson", "omniverse", "doca",
    # NVIDIA data/ML
    "rapids", "cudf", "cuml", "cudnn",
    # NVIDIA audio
    "riva", "nemo", "nemo guardrails",
    # NVIDIA enterprise
    "nvidia nim", "nvidia ai enterprise", "triton inference",
    # Data / MLOps
    "mlops", "kubeflow", "airflow", "dbt", "spark", "kafka", "flink",
    # Reinforcement learning
    "reinforcement learning", "rl", "ppo", "dqn",
    # Use cases (presence alone is a signal)
    "recommendation", "predictive", "anomaly detection", "fraud detection",
    "personalization", "personalização", "credit scoring", "análise de crédito",
    "imagem médica", "diagnóstico", "diagnosis",
    "atendimento", "customer service", "suporte",
    # Common abbreviations seen in Brazilian startup docs
    "ia", "inteligência artificial", "inteligencia artificial",
    "ml", "modelo de ia", "modelo de machine learning", "modelos de ia",
    "redes neurais", "neural network",
}

TECH_KEYWORDS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "vue", "angular", "nextjs", "nodejs", "fastapi", "django", "flask",
    "aws", "azure", "gcp", "kubernetes", "docker", "terraform", "helm",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "tensorflow", "pytorch", "keras", "sklearn", "xgboost", "lightgbm",
    "pandas", "numpy", "scipy", "scikit-learn", "langchain", "llamaindex",
    "openai", "anthropic", "hugging face", "replicate", "groq", "cohere",
    "gradio", "streamlit", "tailwind",
    # NVIDIA stack
    "cuda", "tensorrt", "triton", "cudnn", "cudf", "cuml", "rapids",
    "monai", "clara", "nvidia nvidia", "nvidia nim", "riva", "isaac",
    "omniverse", "nemo guardrails", "nemo", "ai enterprise",
    "gpu cluster", "gpu computing", "inference acceleration",
}

# TAPI §1 anti-wrapper: sinais de defensibilidade / moat
PROPRIETARY_DATA_SIGNS = [
    "dataset próprio", "datasets próprios", "dados internos", "base proprietária",
    "dados históricos", "dados dos clientes geram", "geram dados", "dados rotulados",
    "dados anotados", "exclusivos", "data moat", "dados próprios",
    "clientes geram dados", "treinamento com dados", "corpus interno",
    "inteligência de mercado exclusiva", "dados únicos",
    "bases de dados proprietárias", "dados exclusivos", "dados únicos",
    "registros históricos", "dados históricos exclusivos", "bases proprietárias",
    "dataset único", "datasets únicos", "dados históricos de",
    "proprietary data", "proprietary dataset",
    "bases de histórico de transações", "bases de dados proprietárias",
    "bases proprietárias", "dados históricos de comportamento",
    "inteligência de mercado", "dados de mercado exclusivos",
    "dados financeiros únicos", "bases proprietárias", "bases internas",
    "bases de dados internas", "datasets de produção", "datasets sintéticos",
    "dados de treinamento", "dados de uso de produto",
]

WORKFLOW_SIGNS = [
    "automação end-to-end", "automacao end-to-end", "end-to-end pipeline",
    "integração com erp", "integração erp", "integração crm", "integração com sap",
    "workflow completo", "agentes que executam ações", "agentes que executam",
    "automação de processos", "automacao de processos", "orquestração completa",
    "agentes autônomos", "agentes autonomos", "automação full stack",
    "execução em produção", "automações que executam",
    "pipeline end-to-end", "processos de ponta a ponta", "workflow de ia",
    "loop de feedback", "monitoring, alerting", "mlops com monitoring",
    "previsões por dia", "10k+ previsões", "milhares de previsões",
    "integração de modelo ml", "integração nativa", "integração profunda",
    "automação parcial", "automação full", "mlops com",
]

CUSTOM_MODEL_SIGNS = [
    "fine-tuning", "fine tuning", "treinamos modelo", "treinamento de modelo",
    "treinamos nosso modelo", "modelo próprio", "modelo proprio",
    "modelo customizado", "modelo custom", "rlhf", "lora", "qlora",
    "distilação", "knowledge distillation", "treinamento in-house",
    "modelo treinado in-house", "modelo treinado internamente",
    "modelo fine-tuned", "ajuste fino", "modelo dedicado",
    "modelo de nlp fine-tuned", "llm fine-tuned", "fine-tuned com rlhf",
    "arquitetura proprietária", "ensemble de modelos", "cnn custom",
    "attention mechanism", "modelo vision", "modelo de detecção",
    "autoencoders treinados", "collaborative filtering",
    "fine-tuned com 50b", "treinado com 10m+", "5m imagens",
    "custom model", "custom neural", "in-house model",
    "modelos de machine learning baseados", "modelos baseados em scikit-learn",
    "ensemble de modelos", "modelos de detecção de fraude",
    "modelos de previsão", "modelo de credit scoring",
]

DISTRIBUTION_SIGNS = [
    "b2b enterprise", "contratos com grandes", "marketplace próprio",
    "marketplace proprio", "1000+ clientes", "+1000 clientes",
    "parceiros estratégicos", "parceiros estrategicos", "canal de distribuição",
    "canal proprio de distribuição", "presença em 10+ países",
    "clientes corporativos", "grandes corporações", "grandes corporacoes",
    "grandes empresas", "vendas b2b", "enterprise sales", "clientes globais",
    "50k+ empresas", "milhões de transações", "milhões de",
]

# Sinais típicos de LLM wrapper (TAPI §3)
WRAPPER_SIGNS = [
    "wrapper de openai", "wrapper de gpt", "wrapper de claude", "wrapper de anthropic",
    "integração simples com openai", "integração simples com gpt",
    "interface para chatgpt", "camada sobre openai", "camada sobre gpt",
    "interface sobre llm", "interface para llm", "front-end para openai",
    "resumo de texto via openai", "resumo via gpt", "q&a sobre documentos via openai",
    "chatgpt wrapper", "llm wrapper", "interface para gpt", "integra com openai",
    "powered by openai", "powered by gpt", "prompts pré-feitos",
]


def _match_any(text: str, phrases: list[str]) -> list[str]:
    """Retorna as frases presentes no texto (substring case-insensitive)."""
    found = []
    for p in phrases:
        if p in text:
            found.append(p)
    return found


def extract_from_text(text: str, nome: str, tamanho_time: str = "") -> dict:
    """Extrai perfil estruturado do texto por heurísticas de dicionário.

    Detecta sinais de IA, stack, casos de uso (regex), gaps técnicos e os
    sinais de moat do TAPI §1 (dados proprietários, workflow, modelo custom,
    distribuição) além de indicadores de LLM wrapper.
    """
    text_lower = text.lower() if text else ""

    # AI signals
    sinais_ai = _match_any(text_lower, AI_SIGNALS)

    # Tech stack
    stack = [t for t in TECH_KEYWORDS if t in text_lower]

    # Use cases
    usecase_patterns = [
        (r"atendimento ao cliente", "Customer service"),
        (r"chatbot", "Chatbot"),
        (r"análise de crédito", "Credit analysis"),
        (r"análise de credito", "Credit analysis"),
        (r"detecção de fraude", "Fraud detection"),
        (r"deteccao de fraude", "Fraud detection"),
        (r"recomendação", "Recommendation"),
        (r"recomendacao", "Recommendation"),
        (r"tradução", "Translation"),
        (r"traducao", "Translation"),
        (r"resumo", "Summarization"),
        (r"classificação", "Classification"),
        (r"classificacao", "Classification"),
        (r"geração de código", "Code generation"),
        (r"geracao de codigo", "Code generation"),
        (r"processamento de imagem", "Image processing"),
        (r"ocr", "OCR"),
        (r"voz| speech| tts| asr", "Speech AI"),
        (r"previsão| forecast| predictive", "Predictive analytics"),
        (r"previsao| forecast| predictive", "Predictive analytics"),
        (r"manutenção preditiva", "Predictive maintenance"),
        (r"manutencao preditiva", "Predictive maintenance"),
        (r"diagnóstico médico", "Medical diagnosis"),
        (r"diagnostico medico", "Medical diagnosis"),
        (r"\bsemantic search\b", "Semantic search"),
        (r"\bbusca semântica\b", "Semantic search"),
        (r"\bbusca semantica\b", "Semantic search"),
        (r"\brag\b", "RAG"),
        (r"\bretrieval\b", "RAG"),
    ]
    casos_uso = []
    for pattern, label in usecase_patterns:
        if re.search(pattern, text_lower):
            casos_uso.append(label)

    # Gaps técnicos
    gaps = []
    if "api externa" in text_lower or "external api" in text_lower:
        gaps.append("Depends on external LLM APIs without optimization")
    if " custo" in text_lower and ("api" in text_lower or "llm" in text_lower):
        gaps.append("High inference cost from API-based LLMs")
    if "latência" in text_lower or "latency" in text_lower:
        gaps.append("Latency issues with current inference setup")
    if "gpu" not in text_lower and any(k in text_lower for k in ["modelo", "model", "ml", "ai"]):
        gaps.append("No GPU optimization in current stack")
    if "governança" in text_lower or "compliance" in text_lower:
        gaps.append("AI governance and compliance needs")
    if "dados" in text_lower and "privacidade" in text_lower:
        gaps.append("Data privacy and security concerns")
    if not sinais_ai and ("python" in text_lower or "api" in text_lower):
        gaps.append("No proprietary AI models — using third-party APIs")

    # TAPI §1: extração de moat
    proprietary_data = _match_any(text_lower, PROPRIETARY_DATA_SIGNS)
    workflow_depth = _match_any(text_lower, WORKFLOW_SIGNS)
    custom_model = _match_any(text_lower, CUSTOM_MODEL_SIGNS)
    distribution = _match_any(text_lower, DISTRIBUTION_SIGNS)
    wrapper_indicators = _match_any(text_lower, WRAPPER_SIGNS)

    return {
        "nome": nome,
        "descricao": (text or "")[:2000],
        "stack": list(set(stack))[:10],
        "casos_uso": casos_uso[:5],
        "gaps_identificados": gaps[:5],
        "sinais_ai": sinais_ai[:10],
        "proprietary_data": proprietary_data,
        "workflow_depth": workflow_depth,
        "custom_model": custom_model,
        "distribution": distribution,
        "wrapper_indicators": wrapper_indicators,
        "tamanho_time": str(tamanho_time or ""),
    }


async def extractor(state: AgentState) -> AgentState:
    """Extract structured profiles from retrieved startup documents."""
    startups = state.retrieved_startups or []
    if not startups:
        state.next_agent = "classifier"
        return state

    settings = get_settings()
    all_profiles = []

    for startup in startups:
        nome = startup.get("nome", "")
        sid = startup.get("id")

        docs_texts = []
        try:
            async with DatabaseLoader(settings) as loader:
                async with loader.pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT titulo, conteudo_texto FROM documentos WHERE startup_id = $1 LIMIT 3",
                        sid,
                    )
                    for row in rows:
                        if row["conteudo_texto"]:
                            docs_texts.append(f"{row['titulo'] or ''}\n{row['conteudo_texto']}")
        except Exception as e:
            logger.debug(f"[extractor] Failed to fetch docs for {nome}: {e}")

        if docs_texts:
            combined_text = "\n\n---\n\n".join(docs_texts)
        else:
            combined_text = startup.get("descricao_curta") or ""

        profile = extract_from_text(combined_text, nome, startup.get("tamanho_time", ""))
        profile["site"] = startup.get("site")
        profile["setor"] = startup.get("setor")
        profile["estagio"] = startup.get("estagio")
        profile["localizacao"] = startup.get("localizacao")
        profile["categoria"] = _CURATED_CAT.get(nome, "unknown")
        all_profiles.append(profile)

    state.extracted_profiles = all_profiles
    state.next_agent = "classifier"
    logger.info(f"[extractor] Extracted {len(all_profiles)} profiles")
    return state
