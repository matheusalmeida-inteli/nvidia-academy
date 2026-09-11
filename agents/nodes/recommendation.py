"""Agent 7: Recommendation Agent.

Cross-references startup profile with NVIDIA tech references
to generate prioritized technology recommendations + community actions.
TAPI §1: "atrair, qualificar e nutrir" — community actions para nutrição.

Motor de scoring (NORMALIZADO, RAG como sinal primário):
- score = RAG_WEIGHT * rag_component
       + HARDCODED_WEIGHT * hardcoded_component
       + SECTOR_WEIGHT * sector_component
- Pesos somam 1.0 (RAG 0.6, hardcoded 0.25, sector 0.15)
"""
from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass

from loguru import logger

from agents.state import AgentState

# Pesos do scoring (constantes nomeadas, somam 1.0)
RAG_WEIGHT = 0.6
HARDCODED_WEIGHT = 0.25
SECTOR_WEIGHT = 0.15
assert abs(RAG_WEIGHT + HARDCODED_WEIGHT + SECTOR_WEIGHT - 1.0) < 1e-9, "pesos devem somar 1.0"

MIN_FINAL_SCORE = 0.20
MAX_RECOMMENDATIONS = 6

# Aliases setoriais/textuais: curto-handles ambíguos ("ia", "ml") expandidos
# para os termos explícitos que representam, evitando falso positivo por
# substring ("ia" dentro de "via", "ml" dentro de "mlops" não deve disparar sozinho).
TEXT_ALIASES: dict[str, tuple[str, ...]] = {
    "ia": ("ia", "inteligencia artificial", "inteligência artificial", "ai"),
    "ml": ("ml", "machine learning", "aprendizado de máquina", "aprendizado de maquina"),
}


def _normalize_text(value: str) -> str:
    """Lowercase + strip acentos para matching tolerante a variantes."""
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.combining(c)).lower()


def _collapse(value: str) -> str:
    """Remove tudo que não é [a-z0-9] no texto normalizado (para matching setorial)."""
    return re.sub(r"[^a-z0-9]", "", _normalize_text(value))


def _sector_match(sector_tokens: list[str], sector: str) -> bool:
    """True se algum token de setor casa o valor de setor (normalizado).

    Sectores são domínio fechado (palavras como "fintech", "agro", "saude"),
    então substring no texto colapsado é segura: "Fintech / Pagamentos" casa
    os tokens "fintech"/"pagamentos"; "Logística" casa "logistica".
    """
    collapsed = _collapse(sector)
    if not collapsed:
        return False
    for tok in sector_tokens:
        key = _collapse(tok)
        if key and key in collapsed:
            return True
    return False


def _term_present(tokens: list[str], text_norm: str) -> bool:
    """Matching word-boundary dos termos no texto (com acentos normalizados).

    Termos curtos/ambíguos ("ia", "ml") usam aliases explícitos e exigem
    fronteira de palavra — evita que "ia" dispare dentro de "via"/"material"
    ou que "ml" dispare dentro de "mlops"/"mlflow".
    """
    if not tokens or not text_norm:
        return False
    for tok in tokens:
        forms = TEXT_ALIASES.get(tok.strip().lower(), (tok,))
        for form in forms:
            norm = _normalize_text(form)
            if not norm:
                continue
            if re.search(rf"\b{re.escape(norm)}\b", text_norm):
                return True
    return False


@dataclass
class TechRule:
    """Regra de negócio que associa sinais de perfil a tecnologias NVIDIA.

    Dispara apenas quando todos os termos de `requires_all` estão presentes
    e pelo menos um de `requires_any_of` (ou `sector_boost` casa o setor).
    `requires_wrapper_signal` condiciona a regra a empresas sinalizadas como
    LLM wrapper (risco_wrapper=True).
    """
    id: str
    techs: list[str]
    requires_all: list[str] = None
    requires_any_of: list[str] = None
    sector_boost: list[str] = None
    requires_wrapper_signal: bool = False

    def __post_init__(self):
        """Normaliza listas opcionais para listas vazias."""
        self.requires_all = self.requires_all or []
        self.requires_any_of = self.requires_any_of or []
        self.sector_boost = self.sector_boost or []


# Regras baseadas no vocabulário real do extractor (sinais_ai).
# Vocabulário extraído: llm, machine learning, ia, gpu, ml, nvidia,
# mlops, nlp, tensorrt, cuda, hugging face, tensorflow,
# predictive, analytics, atendimento, recommendation, personalização, etc.
# Cada regra exige requires_all + pelo menos 1 de requires_any_of (ou
# sector_boost) para disparar — elimina o problema de "ml" sozinho
# recomendar RAPIDS/cuDF para qualquer startup.
TECH_RULES: list[TechRule] = [
    TechRule(
        id="grandes_volumes_tabulares",
        requires_all=["ml"],
        requires_any_of=[
            "predictive", "analytics", "hugging face", "tensorflow",
            "kafka", "airflow",
        ],
        sector_boost=["fintech", "logistica", "varejo", "ecommerce", "agro", "industrial"],
        techs=["RAPIDS", "cuDF", "cuML"],
    ),
    TechRule(
        id="llm_atendimento_wrapper",
        requires_all=["llm"],
        requires_any_of=["atendimento", "nlp"],
        requires_wrapper_signal=True,
        techs=["NVIDIA NIM", "NeMo Guardrails", "Triton"],
    ),
    TechRule(
        id="llm_inferencia_producao",
        requires_all=["llm"],
        requires_any_of=[
            "mlops", "tensorrt", "triton",
        ],
        sector_boost=["enterprise"],
        techs=["NVIDIA NIM", "TensorRT-LLM", "Triton"],
    ),
    TechRule(
        id="llm_fine_tuning_custom",
        requires_all=["llm"],
        requires_any_of=["hugging face", "tensorflow", "modelo de machine learning"],
        techs=["NeMo", "NVIDIA NIM"],
    ),
    TechRule(
        id="rag_retrieval",
        requires_all=["llm"],
        requires_any_of=["rag", "retrieval"],
        techs=["NVIDIA NIM", "NeMo"],
    ),
    TechRule(
        id="voz_callcenter",
        requires_all=["ia"],
        requires_any_of=[
            "asr", "tts", "speech", "transcrição", "transcricao",
            "áudio", "audio", "voz",
        ],
        sector_boost=["contact center", "bpo", "telecom"],
        techs=["Riva", "NVIDIA NIM"],
    ),
    TechRule(
        id="imagens_medicas_saude",
        requires_all=["ia"],
        requires_any_of=[
            "imagens médicas", "imagem médica", "medical imaging",
            "diagnóstico", "diagnostico", "radiolog", "patolog",
            "clara", "monai",
        ],
        sector_boost=["health", "saude", "healthcare", "healthtech"],
        techs=["Clara", "MONAI", "NVIDIA NIM"],
    ),
    TechRule(
        id="robotica_simulacao",
        requires_all=["gpu"],
        requires_any_of=[
            "robótica", "robotica", "robotics", "ros2", "jetson",
            "simulação", "simulacao", "digital twin", "omniverse", "isaac",
        ],
        sector_boost=["industrial", "manufatura", "logistica"],
        techs=["Isaac", "Omniverse"],
    ),
    TechRule(
        id="cybersec_ameacas",
        requires_all=["ml"],
        requires_any_of=[
            "cybersec", "ameaça", "ameaca", "fraude", "phishing",
            "detecção de anomalias", "deteccao de anomalias", "fraud detection",
        ],
        sector_boost=["fintech", "financeir"],
        techs=["Morpheus", "RAPIDS"],
    ),
    TechRule(
        id="governanca_agentes",
        requires_all=["llm"],
        requires_any_of=[
            "governança", "governanca", "compliance", "safety", "guardrails",
            "agentes de ia", "ai agents",
        ],
        techs=["NeMo Guardrails", "NVIDIA NIM"],
    ),
    TechRule(
        id="generative_ai_llm_ops",
        requires_all=["llm"],
        requires_any_of=["generativa", "generative", "gpt", "langchain"],
        techs=["NVIDIA NIM", "NeMo", "TensorRT-LLM"],
    ),
    TechRule(
        id="gpu_treinamento_custom",
        requires_all=["gpu"],
        requires_any_of=[
            "cuda", "treinamento in-house", "treinamento de modelo",
            "modelo proprietário", "modelo proprio", "kernels custom",
            "código customizado",
        ],
        techs=["CUDA", "RAPIDS"],
    ),
]


SECTOR_FILTER = {
    # Cuidado de saúde
    "health": {"Clara", "MONAI", "Riva", "NVIDIA NIM"},
    "saúde": {"Clara", "MONAI", "Riva", "NVIDIA NIM"},
    "saude": {"Clara", "MONAI", "Riva", "NVIDIA NIM"},
    "healthcare": {"Clara", "MONAI", "Riva", "NVIDIA NIM"},
    "healthtech": {"Clara", "MONAI", "Riva", "NVIDIA NIM"},
    # Agro
    "agricultura": {"Isaac", "RAPIDS", "cuML"},
    "agro": {"Isaac", "RAPIDS", "cuML"},
    "agtech": {"Isaac", "RAPIDS", "cuML"},
    # Robótica / industrial / manufatura
    "robótica": {"Isaac", "Omniverse", "cuDF", "RAPIDS"},
    "robotica": {"Isaac", "Omniverse", "cuDF", "RAPIDS"},
    "robotics": {"Isaac", "Omniverse", "cuDF", "RAPIDS"},
    "manufacturing": {"Isaac", "Omniverse", "cuDF", "RAPIDS"},
    "manufatura": {"Isaac", "Omniverse", "cuDF", "RAPIDS"},
    "industrial": {"Isaac", "Omniverse", "cuDF", "RAPIDS"},
    # Cybersecurity
    "cybersec": {"Morpheus", "RAPIDS", "cuML", "cuDF"},
    "seguranca": {"Morpheus", "RAPIDS", "cuML", "cuDF"},
    # Finanças / seguros
    "fintech": {"NVIDIA NIM", "RAPIDS", "cuML", "cuDF", "Morpheus", "Riva"},
    "financeir": {"NVIDIA NIM", "RAPIDS", "cuML", "cuDF", "Morpheus", "Riva"},
    "bancos": {"NVIDIA NIM", "RAPIDS", "cuML", "cuDF", "Morpheus"},
    "seguros": {"NVIDIA NIM", "RAPIDS", "cuML", "Morpheus"},
    "insurtech": {"NVIDIA NIM", "RAPIDS", "cuML", "Morpheus"},
    # Logística / transporte / entrega
    "logistica": {"Isaac", "Omniverse", "RAPIDS", "cuDF"},
    "logística": {"Isaac", "Omniverse", "RAPIDS", "cuDF"},
    "transporte": {"Isaac", "Omniverse", "RAPIDS", "cuDF"},
    # Varejo / e-commerce
    "varejo": {"NVIDIA NIM", "Triton", "TensorRT-LLM", "cuML", "RAPIDS"},
    "retail": {"NVIDIA NIM", "Triton", "TensorRT-LLM", "cuML", "RAPIDS"},
    "ecommerce": {"NVIDIA NIM", "Triton", "TensorRT-LLM", "cuML", "RAPIDS"},
    "e-commerce": {"NVIDIA NIM", "Triton", "TensorRT-LLM", "cuML", "RAPIDS"},
    # Telecom / atendimento / BPO
    "telecom": {"Riva", "NVIDIA NIM", "RAPIDS", "cuDF"},
    "contact center": {"Riva", "NVIDIA NIM", "NeMo Guardrails"},
    "bpo": {"Riva", "NVIDIA NIM", "NeMo Guardrails"},
    "atendimento": {"Riva", "NVIDIA NIM", "NeMo Guardrails"},
    # Enterprise / B2B
    "enterprise": {"NVIDIA NIM", "Triton", "TensorRT-LLM", "NeMo"},
    # Marketing / vendas / crescimento
    "marketing": {"NVIDIA NIM", "NeMo"},
    "martech": {"NVIDIA NIM", "NeMo", "Triton"},
    "midia": {"NVIDIA NIM", "NeMo", "Triton"},
    "media": {"NVIDIA NIM", "NeMo", "Triton"},
    # Recursos humanos
    "hr tech": {"NVIDIA NIM", "NeMo", "Riva"},
    "hrtech": {"NVIDIA NIM", "NeMo", "Riva"},
    "recrutamento": {"NVIDIA NIM", "NeMo", "Riva"},
    "rh": {"NVIDIA NIM", "NeMo", "Riva"},
    # Educação
    "educacao": {"NVIDIA NIM", "NeMo", "NeMo Guardrails"},
    "edtech": {"NVIDIA NIM", "NeMo", "NeMo Guardrails"},
    # FoodTech
    "foodtech": {"NVIDIA NIM", "cuML", "RAPIDS"},
    "food": {"NVIDIA NIM", "cuML", "RAPIDS"},
    # PropTech / imobiliário
    "proptech": {"RAPIDS", "cuML", "Omniverse"},
    "imobiliario": {"RAPIDS", "cuML", "Omniverse"},
    # Mobile
    "mobile": {"NVIDIA NIM", "NeMo", "Triton"},
    # Jogos / conteúdo 3D
    "gaming": {"Omniverse", "Isaac"},
    "games": {"Omniverse", "Isaac"},
    # Automação / automotivo / energia
    "automotivo": {"Isaac", "Omniverse", "CUDA"},
    "automotive": {"Isaac", "Omniverse", "CUDA"},
    "energia": {"RAPIDS", "cuDF", "Omniverse"},
    "energy": {"RAPIDS", "cuDF", "Omniverse"},
    # Serviços de TI / infra
    "it services": {"NVIDIA NIM", "Triton", "CUDA"},
    "impressao 3d": {"Omniverse", "CUDA"},
    "erp": {"NVIDIA NIM", "NeMo"},
    "saas": {"NVIDIA NIM", "Triton", "NeMo"},
}


TECH_DEFS = {
    "NVIDIA Inception": ("high", "low",
        "Programa de aceleração — GPU credits, suporte técnico, rede NVIDIA.",
        "Acelera go-to-market e conexões enterprise."),
    "NVIDIA NIM": ("high", "medium",
        "Microserviços otimizados para inferência de LLMs — até 5x mais rápido.",
        "Reduz custo de inferência e latência."),
    "TensorRT-LLM": ("medium", "medium",
        "Otimização LLMs — batching, paged attention, INT8/FP8.",
        "Melhor custo-benefício em inferência de grande escala."),
    "Triton": ("medium", "medium",
        "Serving de modelos em produção com dynamic batching.",
        "Reduce MLOps overhead."),
    "NeMo Guardrails": ("high", "low",
        "Controle programável de comportamento de agentes de IA.",
        "Garante compliance e segurança em produção."),
    "RAPIDS": ("high", "low",
        "Aceleração GPU para ciência de dados — cuDF e cuML.",
        "Processamento 10-100x mais rápido para grandes volumes."),
    "cuML": ("medium", "medium",
        "ML acelerado em GPU — clustering, classificação, séries temporais.",
        "Treinamento mais rápido e iteração de modelo acelerada."),
    "Riva": ("high", "medium",
        "ASR e TTS neural em tempo real com suporte a Português.",
        "Interfaces de voz sub-300ms."),
    "Clara": ("medium", "high",
        "IA para healthcare — imagens médicas e genômica.",
        "Diferenciação técnica em produto de saúde."),
    "Isaac": ("medium", "high",
        "Simulação de robótica e deployment em Jetson/ROS2.",
        "Time-to-market acelerado para robótica."),
    "Morpheus": ("medium", "medium",
        "ML pipeline para detecção de ameaças em tempo real.",
        "SOC mais eficiente com menos falsos positivos."),
    "AI Enterprise": ("low", "low",
        "Plataforma enterprise com suporte SLA e compliance.",
        "Facilita procurement em clientes enterprise."),
    "NeMo": ("medium", "medium",
        "Fine-tuning e RLHF de LLMs com frameworks NVIDIA.",
        "Customização de modelos para casos de uso específicos."),
    "cuDF": ("medium", "low",
        "DataFrame GPU compatível com pandas — ETL 10x mais rápido.",
        "Processamento de dados mais rápido."),
    "CUDA": ("medium", "high",
        "Programação paralela em GPU para kernels customizados.",
        "Máximo desempenho para operações proprietárias."),
    "AI Services": ("medium", "low",
        "Serviços de IA pré-construídos para visão, fala e documentos.",
        "Time-to-market rápido para casos de uso comuns."),
    "AI-Native Services": ("high", "low",
        "Stack de microservices NVIDIA para aplicações cloud-native.",
        "Infraestrutura otimizada para deployment em escala."),
    "MONAI": ("medium", "high",
        "IA para análise de imagens médicas e genômica — compatibilidade com DICOM e workflow de radiologia.",
        "Diferenciação técnica em produto de saúde com compatibilidade PACS"),
    "Omniverse": ("medium", "low",
        "Plataforma de colaboração 3D e simulação física para equipes criativas e industriais.",
        "Time-to-market rápido para casos de uso comuns em design e engenharia"),
}


CANONICAL_NAMES = {
    "NVIDIA Morpheus": "Morpheus",
    "NVIDIA Clara": "Clara",
    "NVIDIA NIM": "NVIDIA NIM",
    "NVIDIA AI Enterprise": "AI Enterprise",
    "NVIDIA Triton Inference Server": "Triton",
    "NVIDIA Triton": "Triton",
    "NVIDIA Isaac": "Isaac",
    "NVIDIA Riva": "Riva",
    "NVIDIA MONAI": "MONAI",
    "MONAI": "MONAI",
    "NVIDIA AI Services": "AI Services",
    "AI-Native Services": "AI-Native Services",
    "AI Services": "AI Services",
    "NVIDIA Omniverse": "Omniverse",
    "NeMo": "NeMo",
    "NeMo Guardrails": "NeMo Guardrails",
    "TensorRT-LLM": "TensorRT-LLM",
    "NVIDIA NeMo": "NeMo",
    "NVIDIA RAPIDS": "RAPIDS",
}

# Fonte canônica por tech (documentação oficial NVIDIA) — ancorou recomendações
# vindas de REGRA DE NEGÓCIO (sem evidência RAG recuperada) com um link
# oficial verificável (TAPI §5.5: recomendações precisam de fonte).
CANONICAL_SOURCES: dict[str, dict[str, str]] = {
    "NVIDIA Inception": {"titulo": "NVIDIA Inception", "url": "https://www.nvidia.com/en-us/startups/"},
    "NVIDIA NIM": {"titulo": "NVIDIA NIM", "url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/"},
    "TensorRT-LLM": {"titulo": "TensorRT-LLM", "url": "https://github.com/NVIDIA/TensorRT-LLM"},
    "Triton": {"titulo": "Triton Inference Server", "url": "https://developer.nvidia.com/triton-inference-server"},
    "NeMo Guardrails": {"titulo": "NeMo Guardrails", "url": "https://github.com/NVIDIA/NeMo-Guardrails"},
    "NeMo": {"titulo": "NVIDIA NeMo", "url": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/"},
    "cuML": {"titulo": "RAPIDS cuML", "url": "https://developer.nvidia.com/rapids"},
    "RAPIDS": {"titulo": "RAPIDS", "url": "https://developer.nvidia.com/rapids"},
    "cuDF": {"titulo": "RAPIDS cuDF", "url": "https://developer.nvidia.com/rapids"},
    "Riva": {"titulo": "NVIDIA Riva", "url": "https://developer.nvidia.com/riva"},
    "Clara": {"titulo": "NVIDIA Clara", "url": "https://www.nvidia.com/en-us/clara/"},
    "Isaac": {"titulo": "NVIDIA Isaac", "url": "https://developer.nvidia.com/isaac"},
    "Morpheus": {"titulo": "NVIDIA Morpheus", "url": "https://developer.nvidia.com/morpheus-cybersecurity"},
    "CUDA": {"titulo": "NVIDIA CUDA Toolkit", "url": "https://developer.nvidia.com/cuda-toolkit"},
    "AI-Native Services": {"titulo": "NVIDIA AI Native Services", "url": "https://www.nvidia.com/en-us/ai/"},
    "AI Services": {"titulo": "NVIDIA AI Services", "url": "https://www.nvidia.com/en-us/ai/"},
    "AI Enterprise": {"titulo": "NVIDIA AI Enterprise", "url": "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/"},
    "MONAI": {"titulo": "MONAI", "url": "https://monai.io"},
    "Omniverse": {"titulo": "NVIDIA Omniverse", "url": "https://www.nvidia.com/en-us/omniverse/"},
    "cuDNN": {"titulo": "NVIDIA cuDNN", "url": "https://developer.nvidia.com/cudnn"},
    "DeepStream": {"titulo": "NVIDIA DeepStream", "url": "https://developer.nvidia.com/deepstream-sdk"},
    "FLARE": {"titulo": "NVIDIA FLARE", "url": "https://developer.nvidia.com/flare"},
    "TAO": {"titulo": "NVIDIA TAO", "url": "https://developer.nvidia.com/tao"},
    "TensorRT": {"titulo": "NVIDIA TensorRT", "url": "https://developer.nvidia.com/tensorrt"},
}

# Famílias de techs NVIDIA que resolvem o MESMO caso de uso (overlap alto).
# Recomendação consolida por família — mantém apenas o membro de maior score —
# reduzindo ruído quando RAPIDS/cuDF/cuML ou NIM/NeMo/TensorRT-LLM surgem juntos.
TECH_FAMILIES: dict[str, list[str]] = {
    "accelerated_data": ["RAPIDS", "cuDF", "cuML"],
    "llm_runtime": ["NVIDIA NIM", "NeMo", "TensorRT-LLM"],
}


def _canonical(tech: str) -> str:
    """Normaliza o nome de tecnologia NVIDIA para o nome canônico."""
    return CANONICAL_NAMES.get(tech, tech)


def _build_rag_justification(references: list[dict], tech: str) -> tuple[str, dict | None]:
    """Reúne a justificativa RAG (título+trecho) e a fonte da primeira referência da tech."""
    for ref in references:
        if _canonical(ref.get("tech", "")) == tech:
            title = ref.get("title", "")
            content = ref.get("content", "")[:300]
            score = ref.get("rerank_score", 0) or ref.get("score", 0)
            if content:
                text = f"{title}: {content}..."
                fonte = {
                    "titulo": title,
                    "url": ref.get("url", ""),
                    "tecnologia": ref.get("tech", ""),
                    "categoria": ref.get("category", ""),
                    "score_rerank": round(score, 3) if score else None,
                    "trecho": content[:200],
                }
                return text, fonte
    return "", None


async def _synthesize_justification(
    tech: str,
    base: str,
    fontes: list[dict],
    gaps: list[str],
) -> str:
    """Síntese LLM da justificativa técnica com citações (TAPI §5.3 passo 8).

    Quando RAG_SYNTHESIZE=1, há LLM disponível e existem fontes RAG, retorna a
    justificativa sintetizada (qual o encaixe técnico + evidência citada). Em
    qualquer falha/indisponibilidade, mantém o texto determinístico (reference
    card) — resiliência offline e custo zero por padrão.
    """
    try:
        from rag.config import rag_synthesize_enabled
        if not rag_synthesize_enabled():
            return base
    except Exception:
        return base
    if not fontes:
        return base
    try:
        from agents.llm import llm
        if not llm.is_available():
            return base
    except Exception:
        return base

    titulos = "; ".join(f.get("titulo", "") for f in fontes if f.get("titulo"))
    urls = "; ".join(f.get("url", "") for f in fontes if f.get("url"))
    system = (
        "Você é um engenheiro de soluções NVIDIA. Gere UMA justificativa técnica "
        "com citações (1-2 frases) explicando POR QUE a tecnologia se encaixa nos "
        "gaps da startup, usando as fontes recuperadas como evidência. Não invente "
        "capacidades ausentes nas fontes. Responda apenas com a justificativa."
    )
    user = (
        f"Tecnologia: {tech}\n"
        f"Gaps/necessidades identificados: {', '.join(gaps) if gaps else 'geral'}\n"
        f"Fontes RAG recuperadas:\n{titulos}\nURLs: {urls}\n"
        f"Reescrita base atual (fallback): {base}"
    )
    try:
        synth = (await llm.complete(system, user, max_tokens=160) or "").strip()
        if len(synth) >= 40:
            return synth
    except Exception as e:
        logger.warning(f"[recommendation] síntese falhou ({e}); fallback para reference card")
    return base


def _evaluate_rules(
    text_all: str,
    setor: str,
    risco_wrapper: bool,
) -> dict[str, list[str]]:
    """Avalia regras e retorna {tech: [regra_id,...]} que dispararam."""
    matched_techs: dict[str, list[str]] = {}
    text_norm = _normalize_text(text_all)
    setor_lower = setor.lower()

    for rule in TECH_RULES:
        # requires_all: TODOS devem aparecer (word-boundary, acentos normalizados)
        if rule.requires_all and not _term_present(rule.requires_all, text_norm):
            continue

        # requires_any_of: pelo menos UM deve aparecer no texto (não no setor)
        # sector_boost é independente e só ativa se a regra NÃO tem requires_any_of
        has_text_match = (
            rule.requires_any_of and _term_present(rule.requires_any_of, text_norm)
        )
        has_sector_match = (
            rule.sector_boost and _sector_match(rule.sector_boost, setor_lower)
        )
        # Lógica: regra dispara se:
        # - Tem requires_any_of E há match no texto, OU
        # - Não tem requires_any_of E há sector_boost match (regras puramente setoriais)
        # OU (para regras com requires_any_of E sector_boost) se texto match OU sector boost
        # Mantém comportamento original de forma mais explícita:
        if rule.requires_any_of:
            # Com requires_any_of: texto match é obrigatório
            if not has_text_match:
                continue
        elif rule.sector_boost:
            # Sem requires_any_of mas com sector_boost: sector match é obrigatório
            if not has_sector_match:
                continue
        # else: sem requires_any_of nem sector_boost — só requires_all basta

        # wrapper gate
        if rule.requires_wrapper_signal and not risco_wrapper:
            continue

        for tech in rule.techs:
            matched_techs.setdefault(tech, []).append(rule.id)

    return matched_techs


def _proxima_acao_for(tech: str, origem: str, regra_ids: list[str], complex: str) -> str:
    """Gera a próxima ação concreta conforme origem (RAG/regra) e regra disparada."""
    regra = regra_ids[0] if regra_ids else ""

    acao_rag = {
        "llm_inferencia_producao": "Agendar call técnica com time NVIDIA NIM para avaliar modelo de serving e requisitos de throughput.",
        "llm_atendimento_wrapper": "Discutir arquitetura com NeMo Guardrails: como integrar com pipeline de atendimento existente.",
        "llm_fine_tuning_custom": "Avaliar NeMo vs. Hugging Face PEFT: comparar custo de fine-tuning vs. resultados em benchmarks.",
        "rag_retrieval": "Prototipar RAG com NVIDIA NIM embeddings: testar relevancia vs. BM25 baseline em dataset interno.",
        "voz_callcenter": "Solicitar trial da Riva API: validar WER <5% em Português brasileiro com dados de produção.",
        "imagens_medicas_saude": "Verificar compatibilidade do modelo com DICOM: integrar com fluxo PACS existente.",
        "robotica_simulacao": "Rodar benchmark Isaac Sim: validar physics fidelity vs. ROS2 Gazebo em cenário pick-and-place.",
        "cybersec_ameacas": "Piloto Morpheus em fluxo de logs: medir false-positive rate vs. rule-based baseline.",
        "governanca_agentes": "Definir taxonomy de guardrails com time de compliance: quais ações são aceitáveis para o agente.",
        "generative_ai_llm_ops": "Revisar custos de inferência com TensorRT-LLM: quantificar economia vs. vLLM/bitsandbytes.",
        "gpu_treinamento_custom": "Perfilar kernels CUDA com Nsight: identificar bottlenecks de memória vs. computação.",
        "grandes_volumes_tabulares": "Benchmark RAPIDS vs. pandas/dask: medir speedup em workload ETL real (>10M rows).",
    }

    acao_fallback = {
        "llm_inferencia_producao": "Pesquisar NVIDIA NIM no developer portal: requisitos de GPU, pricing e modelos disponíveis.",
        "llm_atendimento_wrapper": "Ler documentação NeMo Guardrails: casos de uso e integração com LangChain/LlamaIndex.",
        "llm_fine_tuning_custom": "Estudar NeMo curriculum learning: comparar com LoRA/QLoRA em termos de qualidade e custo.",
        "rag_retrieval": "Explorar NVIDIA NIM para embedding: integrar com Qdrant e validar qualidade de retrieval.",
        "voz_callcenter": "Testar Riva ASR free tier: validar acurácia em áudios de call center brasileiro.",
        "imagens_medicas_saude": "Avaliar Clara MONAI: verificar modelos pré-treinados para radiology e pathology.",
        "robotica_simulacao": "Verificar Isaac access via NVIDIA Inception: requisitar trial developer.",
        "cybersec_ameacas": "Estudar Morpheus reference architecture: avaliar fit para pipeline de SOC.",
        "governanca_agentes": "Ler best practices NeMo Guardrails: definir política de segurança para agentes.",
        "generative_ai_llm_ops": "Calcular TCO TensorRT-LLM: comparar com alternativas open-source em custo por token.",
        "gpu_treinamento_custom": "Revisar CUDA best practices: identificar quick wins em kernels críticos.",
        "grandes_volumes_tabulares": "Testar RAPIDS em instância com GPU: validar speedup vs. CPU em ETL real.",
    }

    iftech_rag = {
        "NVIDIA NIM": "Revisar NIM microservice docs: verificar modelos disponíveis e requisitos de deployment.",
        "TensorRT-LLM": "Benchmark TensorRT-LLM com modelo da startup: medir latência e throughput por GPU.",
        "Triton": "Avaliar Triton inference server: testar dynamic batching com workload de produção.",
        "NeMo Guardrails": "Prototipar guardrails com dados de atendimento: definir topics permitidos/bloqueados.",
        "NeMo": "Comparar NeMo vs. Hugging Face Trainer: avaliar qualidade de fine-tuning em tarefa target.",
        "cuML": "Rodar benchmark cuML vs. scikit-learn: medir speedup em algoritmo de ML mais custoso.",
        "RAPIDS": "Piloto RAPIDS com DataFrame real: validar que não há regression em resultados numéricos.",
        "cuDF": "Substituir operações pandas críticas por cuDF: medir ganho em tempo de execução.",
        "Riva": "Testar Riva ASR+TTS com sample de calls: validar em ambiente de staging.",
        "Clara": "Avaliar ClaraMONAI para modality específico: validar compatibilidade com dados DICOM.",
        "Isaac": "Rodar simulação em Isaac Sim: validar physics e rendering para use case target.",
        "Morpheus": "Piloto Morpheus com log stream: mensurar redução de false positives.",
        "CUDA": "Perfilar código com Nsight: identificar kernel mais custoso para otimização.",
        "AI-Native Services": "Revisar arquitetura AI-Native services: avaliar fit para cloud-native deployment.",
        "MONAI": "Validar MONAI com DICOM: fluxo de radiologia e PACS com GPU.",
        "Omniverse": "Validar Omniverse com time de engenharia: digital twin em simulação física.",
    }

    iftech_fallback = {
        "NVIDIA NIM": "Visitar nvidia.com/nim: entender lineup de microserviços e pricing.",
        "TensorRT-LLM": "Ler docs TensorRT-LLM: setup e benchmarks em GPUs NVIDIA.",
        "Triton": "Explorar Triton docs: entender dynamic batching e model ensemble.",
        "NeMo Guardrails": "Ver tutorial NeMo Guardrails: primeiro exemplo de chatbot seguro.",
        "NeMo": "Acessar NeMo GitHub: explorar fine-tuning examples para LLM.",
        "cuML": "Rodar quickstart cuML: primeiro exemplo de ML acelerado em GPU.",
        "RAPIDS": "Instalar RAPIDS via conda/docker: testar cuDF com dataset sample.",
        "cuDF": "Follow RAPIDS quickstart: substituir 3 operações pandas por cuDF.",
        "Riva": "Acessar Riva developer page: solicitar free trial credits.",
        "Clara": "Ver NVIDIA Clara landing page: verificar healthcare solutions.",
        "Isaac": "Verificar Isaac developer program: requisitar acesso via Inception.",
        "Morpheus": "Ler Morpheus getting started: entender pipeline de threat detection.",
        "CUDA": "Revisar CUDA programming guide: primeiro kernel em PyTorch.",
        "AI-Native Services": "Explorar NVIDIA AI Services docs: entender arquitetura cloud-native.",
        "MONAI": "Explorar MONAI docs: integração com DICOM e workflow de radiologia.",
        "Omniverse": "Explorar Omniverse docs: collaboration 3D e digital twins.",
    }

    iftech = iftech_rag if origem in ("rag", "rag_e_regra") else iftech_fallback
    acao_by_regra = acao_rag if origem in ("rag", "rag_e_regra") else acao_fallback

    if regra and regra in acao_by_regra:
        return acao_by_regra[regra]
    if tech in iftech:
        return iftech[tech]
    iftech_default = f"Explorar documentação oficial da NVIDIA para {tech}: especificações técnicas e roadmap."
    return iftech_default


def _compute_sector_boost(tech: str, setor: str) -> bool:
    """Verifica se a tech recebe reforço setorial (combina com o setor da startup)."""
    if not setor:
        return False
    for sec, techs in SECTOR_FILTER.items():
        if _sector_match([sec], setor) and tech in techs:
            return True
    return False


def _family_of(tech: str) -> str | None:
    """Return the family id containing tech, else None."""
    for fam_id, members in TECH_FAMILIES.items():
        if tech in members:
            return fam_id
    return None


def _consolidate_families(scored: list[dict]) -> list[dict]:
    """Collapse tech families to their highest-scoring member.

    Input scored is already sorted by score desc. For each family, the first
    (highest-score) member is kept; siblings with lower scores are dropped to
    avoid redundant recommendations covering the same need.
    """
    seen_family: set[str] = set()
    consolidated: list[dict] = []
    for entry in scored:
        fam = _family_of(entry["tech"])
        if fam is not None:
            if fam in seen_family:
                continue
            seen_family.add(fam)
        consolidated.append(entry)
    return consolidated


def _fallback_def(tech: str) -> tuple[str, str, str, str]:
    """Definição de fallback para techs NVIDIA ainda não mapeadas em TECH_DEFS.

    Em vez de devolver um placeholder genérico ('Tecnologia NVIDIA para X.'),
    gera uma justificativa mínima porém informativa, usando o nome da tech,
    e registra a lacuna para expansão futura do dectado.
    """
    nice = tech.strip()
    if not nice:
        nice = "NVIDIA"
    return (
        "medium",
        "medium",
        (
            f"Solução NVIDIA {nice} relevante para o caso de uso da startup — "
            f"avaliar integração técnica com o stack atual."
        ),
        (
            f"Recurso NVIDIA {nice} amplia a proposta de valor — verificar pricing e "
            f"disponibilidade na região antes de propor."
        ),
    )


def recommend_for(
    profile: dict,
    references: list[dict],
    classification: dict,
) -> list[dict]:
    """Gera recomendações priorizadas. RAG é o sinal primário."""
    gaps = profile.get("gaps_identificados", [])
    cases = profile.get("casos_uso", [])
    sinais = profile.get("sinais_ai", [])
    setor = (profile.get("setor") or "").lower()
    risco_wrapper = bool(classification.get("risco_wrapper"))
    text_all = " ".join(gaps + cases + list(sinais)).lower()

    # Pool de techs: rag_techs ∪ matched_rules
    rag_techs: dict[str, float] = {}
    for r in references:
        canon = _canonical(r.get("tech", ""))
        score = r.get("rerank_score", 0) or r.get("score", 0)
        if score > 0.2 and (canon not in rag_techs or score > rag_techs[canon]):
            rag_techs[canon] = score

    # Presence de evidência RAG por tech (independe do valor de score, que em
    # modo fallback fica < 0.5). Usado para rotular origem corretamente.
    rag_evidence: set[str] = {
        _canonical(r.get("tech", ""))
        for r in references
        if (r.get("content") or "").strip()
    }

    matched_rules = _evaluate_rules(text_all, setor, risco_wrapper)

    all_techs: dict[str, dict] = {}
    for tech, rag_score in rag_techs.items():
        all_techs[tech] = {"rag_score": rag_score, "matched": False, "regra_ids": []}
    for tech, regra_ids in matched_rules.items():
        if tech not in all_techs:
            all_techs[tech] = {"rag_score": 0.0, "matched": True, "regra_ids": regra_ids}
        else:
            all_techs[tech]["matched"] = True
            all_techs[tech]["regra_ids"] = regra_ids

    # Compatibilidade setorial (TAPI §5.5): as techs do SECTOR_FILTER recebem
    # reforço no scoring (sector_component) e delimitam o que a REGRA de negócio
    # pode propor por setor. Techs com evidência RAG real NUNCA são descartadas
    # mesmo fora da lista setorial — evita perder sinais fortes de retrieval.
    setor_lower = setor.lower()
    matched_sector_keys = [k for k in SECTOR_FILTER if _sector_match([k], setor_lower)]
    if matched_sector_keys:
        allowed_by_sector: set[str] = set()
        for key in matched_sector_keys:
            allowed_by_sector.update(SECTOR_FILTER[key])
        all_techs = {
            tech: info
            for tech, info in all_techs.items()
            if tech in allowed_by_sector
            or info["rag_score"] >= 0.5
            or tech in rag_evidence
        }
    # Se nenhum setor casar, todas as techs são mantidas (sem restrição).
# Scoring
    scored: list[dict] = []
    for tech, info in all_techs.items():
        rag_component = info["rag_score"]
        hardcoded_component = 1.0 if info["matched"] else 0.0
        sector_component = 1.0 if _compute_sector_boost(tech, setor) else 0.0

        score = (
            RAG_WEIGHT * rag_component
            + HARDCODED_WEIGHT * hardcoded_component
            + SECTOR_WEIGHT * sector_component
        )

        if score < MIN_FINAL_SCORE:
            continue

        # RAG evidence: thorough score OR real citation presence (fallback
        # scores tend < 0.5, so presence is the reliable signal there).
        has_rag = (rag_component >= 0.5) or (tech in rag_evidence)

        if has_rag and hardcoded_component >= 1.0:
            origem = "rag_e_regra"
        elif has_rag:
            origem = "rag"
        elif hardcoded_component >= 1.0:
            origem = "regra_de_negocio"
        else:
            origem = "fraca"

        scored.append({
            "tech": tech,
            "score": score,
            "rag_component": rag_component,
            "hardcoded_component": hardcoded_component,
            "sector_component": sector_component,
            "origem": origem,
            "regra_ids": info["regra_ids"],
        })

    scored.sort(key=lambda x: -x["score"])

    # Consolidate tech families: keep the highest-scoring member of each
    # overlapping family so RAPIDS/cuDF/cuML don't all appear for one need.
    scored = _consolidate_families(scored)

    # Log de score_breakdown (Parte 4)
    startup_nome = profile.get("nome", "?")
    for entry in scored[:MAX_RECOMMENDATIONS]:
        logger.debug(
            "score_breakdown startup=%s tech=%s rag=%.3f hardcoded=%.3f "
            "sector=%.3f score_final=%.3f origem=%s regra_ids=%s",
            startup_nome, entry["tech"],
            entry["rag_component"], entry["hardcoded_component"],
            entry["sector_component"], entry["score"], entry["origem"],
            entry["regra_ids"],
        )

    # Monta output
    recommendations: list[dict] = []
    for entry in scored[:MAX_RECOMMENDATIONS]:
        tech = entry["tech"]
        prio, complex, just_tech, just_negocio = TECH_DEFS.get(
            tech, _fallback_def(tech)
        )
        rag_just, fonte = _build_rag_justification(references, tech)
        if rag_just:
            just_tech = rag_just

        if entry["origem"] == "regra_de_negocio":
            just_tech = (
                f"[Sem evidência RAG específica — regra TAPI §5.5] {just_tech}"
            )

        fontes_rag = [fonte] if fonte else []
        if not fontes_rag and entry["origem"] == "regra_de_negocio":
            # Recomendações por regra ainda assim carregam fonte verificável:
            # documentação oficial da tech (TAPI §5.5).
            source = CANONICAL_SOURCES.get(tech)
            if source:
                fontes_rag = [source]
        evidencia_texto = (
            f"Regra TAPI: {', '.join(entry['regra_ids'])}"
            if entry["regra_ids"]
            else ("Evidência RAG" if fonte else "Sem evidência específica")
        )

        # proxima_acao varia por origem + regra + complexidade
        proxima_acao = _proxima_acao_for(
            tech, entry["origem"], entry["regra_ids"], complex
        )

        recommendations.append({
            "tecnologia": tech,
            "justificativa_tecnica": just_tech,
            "justificativa_negocio": just_negocio,
            "prioridade": prio,
            "complexidade": complex,
            "proxima_acao": proxima_acao,
            "evidencias": [evidencia_texto],
            "fontes_rag": fontes_rag,
            "origem_recomendacao": entry["origem"],
            "score_final": round(entry["score"], 3),
            "score_breakdown": {
                "rag": round(entry["rag_component"], 3),
                "hardcoded": round(entry["hardcoded_component"], 3),
                "sector": round(entry["sector_component"], 3),
            },
            "regra_ids": entry["regra_ids"],
        })

    return recommendations


def community_actions_for(profile: dict, classif: dict) -> list[str]:
    """TAPI §2(6) — ações comunitárias por setor/estágio/categoria."""
    engagement = []
    education = []
    setor = (profile.get("setor") or "").lower()
    estagio = (profile.get("estagio") or "").lower()
    categoria = classif.get("categoria", "unknown")
    moat = classif.get("moat_score", 0.0)
    fit = classif.get("inception_fit_score", 0.0)

    if categoria in ("ai_native", "ai_enabled"):
        if fit >= 0.5:
            engagement.append("Adicionar à lista de Inception Capital Connect (exposição a investidores)")
        if moat >= 2.0:
            engagement.append("Indicar para fala/painel no NVIDIA GTC (AI-native com moat)")
        if categoria == "ai_native":
            engagement.append("Convidar para programa de mentoria NVIDIA Inception Brasil")

    if any(k in setor for k in ("saúde", "health", "healthcare")):
        engagement.append("Intro para time NVIDIA Clara Brasil — workshop de IA em saúde")
        engagement.append("Indicar para Healthcare AI Forum da NVIDIA")
    elif any(k in setor for k in ("industrial", "manufatura", "iot")):
        engagement.append("Convite para Omniverse Enterprise User Group LATAM")
        engagement.append("Workshop de digital twins com Isaac/Omniverse")
    elif any(k in setor for k in ("fintech", "financeir")):
        engagement.append("Peer intro com outra fintech do portfolio Inception Brasil")
        engagement.append("Convite para NVIDIA Fintech Day LATAM")
    elif any(k in setor for k in ("agro", "agricultura", "agtech")):
        engagement.append("Intro com AgTech do portfolio Inception (peer mentoring)")
    elif any(k in setor for k in ("robótica", "robotics", "drone")):
        engagement.append("Acesso ao Jetson Orin developer kit via Inception")

    if "pre-seed" in estagio or "seed" in estagio:
        engagement.append("Demo day NVIDIA Inception Brasil — pitch slot")
        engagement.append("Mentoria com founders do portfolio (peer learning)")
    elif "serie_a" in estagio or "serie_b" in estagio:
        engagement.append("NVIDIA Capital Connect — exposure a fundos LATAM")
        engagement.append("Joint webinar com outra startup Inception do mesmo setor")

    if classif.get("risco_wrapper"):
        education.append("Workshop 'Como construir defensibilidade' — foco em dados próprios")
        education.append("Sessão técnica: de wrapper para AI-native (roadmap de transição)")
        education.append("Estudo de caso: como startups do Inception migraram de APIs para modelos próprios")

    if fit < 0.35:
        education.append("Convite para meetup NVIDIA AI Brasil (SP ou RJ) — imersão")
        education.append("Newsletter NVIDIA Inception — incluir em updates mensais")

    if not engagement and not education:
        engagement.append("Newsletter NVIDIA Inception — incluir em updates mensais")
        engagement.append("Convite para meetup NVIDIA AI Brasil (SP ou RJ)")

    combined = []
    combined.extend(education[:2])
    combined.extend([a for a in engagement if a not in combined])
    return combined[:4]


async def recommendation(state: AgentState) -> AgentState:
    """Cruza perfis, classificações e referências RAG e produz recomendações por startup."""
    profiles = state.extracted_profiles or []
    classifications = state.classifications or []
    references = state.nvidia_references or []
    rec_map = {r["nome"]: r["references"] for r in references}

    # Síntese LLM com citações (TAPI §5.3-8): apenas recomendações ancoradas
    # em RAG, limitado aos 2 primeiros itens p/ controlar latência/custo.
    # Paralelizada com semáforo (mesmo padrão do nvidia_rag) — 24 calls
    # seriais viraram ~4 concorrentes; sem chave LLM continua instantânea.
    rag_concurrency = max(int(getattr(state, "rag_concurrency", 6) or 1), 1)
    _sem = asyncio.Semaphore(rag_concurrency)

    async def _synth(rec: dict, gaps: list[str]) -> None:
        fontes = rec.get("fontes_rag") or []
        if rec.get("origem_recomendacao") in ("rag", "rag_e_regra") and fontes:
            async with _sem:
                rec["justificativa_tecnica"] = await _synthesize_justification(
                    rec["tecnologia"], rec["justificativa_tecnica"], fontes, gaps
                )

    synth_tasks: list[asyncio.Future] = []
    all_recommendations = []
    for profile in profiles:
        nome = profile.get("nome", "")
        classif = next(
            (c for c in classifications if c.get("nome") == nome), {}
        )
        refs = rec_map.get(nome, [])
        recs = recommend_for(profile, refs, classif)
        gaps = list(profile.get("gaps_identificados") or [])
        synth_tasks.extend(_synth(rec, gaps) for rec in recs[:2])
        community = community_actions_for(profile, classif)
        all_recommendations.append({
            "nome": nome,
            "categoria": classif.get("categoria", "unknown"),
            "confianca": classif.get("confianca", 0),
            "risco_wrapper": classif.get("risco_wrapper", False),
            "moat_score": classif.get("moat_score", 0.0),
            "inception_fit_score": classif.get("inception_fit_score", 0.0),
            "fit_breakdown": classif.get("fit_breakdown", {}),
            "recomendacoes": recs,
            "community_actions": community,
        })

    await asyncio.gather(*synth_tasks)

    state.recommendations = all_recommendations
    state.next_agent = "briefing"
    logger.info(f"[recommendation] Generated recs for {len(all_recommendations)} startups")
    return state
