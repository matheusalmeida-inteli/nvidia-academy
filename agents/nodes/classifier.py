"""Agent 4: Classifier.

TAPI §1 / §3 — "atrair, qualificar e nutrir" e anti-wrapper.

Categorias (TAPI §5.1 — apenas 3):
- ai_native: AI é o core do produto, COM defensibilidade (moat >= 2.0)
- ai_enabled: AI augmenta um business existente (sinais de AI presentes)
- non_ai: não usa AI significativo

Sinal auxiliar (NÃO é categoria):
- risco_wrapper: bool — detecção de LLM wrapper fraco (via _is_llm_wrapper).
  Não sobrescreve a categoria; a inferência por texto tem prioridade.

Decisão de categoria: inferida POR TEXTO primeiro (moat + sinais +
casos_uso). O campo `categoria` do seed existe para gabarito/validação
e serve apenas como ajuste de confiança, nunca como override.

Além da categoria, calcula:
- moat_score (0-5): dados proprietários + workflow + custom model + distribuição
- inception_fit_score (0-1): recomendação para Inception Program
"""
from __future__ import annotations

from loguru import logger

from agents.state import AgentState

AI_NATIVE_SIGNALS = {
    "llm", "gpt", "langchain", "langgraph", "rag", "generative",
    "generativa", "generative ai", "ai agent",
    "ai platform", "mlops", "llmops", "fine-tuning", "model serving",
    "vector db", "embedding", "nlp platform", "computer vision platform",
}

AI_ENABLED_SIGNALS = {
    "machine learning", "ml", "deep learning", "predictive",
    "recommendation", "fraud detection", "anomaly detection",
    "nlp", "nlu", "ocr", "asr", "tts", "voice",
    "tensorflow", "pytorch", "sklearn", "xgboost",
    "chatbot", "ai", "inteligência artificial",
}

# Setores estratégicos para NVIDIA Inception (peso +)
STRATEGIC_SECTORS = {
    "saúde": 0.9,
    "health": 0.9,
    "healthcare": 0.9,
    "industrial": 0.85,
    "manufatura": 0.85,
    "manufacturing": 0.85,
    "iot": 0.8,
    "agro": 0.8,
    "agricultura": 0.8,
    "agtech": 0.8,
    "fintech": 0.75,
    "logística": 0.75,
    "logistics": 0.75,
    "robótica": 0.9,
    "robotics": 0.9,
    "cibersegurança": 0.85,
    "cybersecurity": 0.85,
    "educação": 0.6,
    "edtech": 0.6,
    "varejo": 0.65,
    "retail": 0.65,
    "e-commerce": 0.65,
    "ecommerce": 0.65,
}


def _compute_moat(profile: dict) -> float:
    """TAPI §1 — Defensibilidade da startup (0-5)."""
    score = 0.0
    score += min(2.0, len(profile.get("proprietary_data", [])) * 0.5)
    score += min(1.5, len(profile.get("workflow_depth", [])) * 0.5)
    score += min(2.0, len(profile.get("custom_model", [])) * 0.5)
    score += min(1.0, len(profile.get("distribution", [])) * 0.4)

    # Penalidades
    if profile.get("wrapper_indicators"):
        score -= 0.8
    if not profile.get("custom_model") and profile.get("sinais_ai"):
        # AI mas sem modelo próprio
        score -= 0.4
    if not profile.get("proprietary_data") and profile.get("sinais_ai"):
        # AI mas sem dados próprios
        score -= 0.3

    return max(0.0, min(5.0, round(score, 2)))


def _is_llm_wrapper(profile: dict, moat: float) -> bool:
    """TAPI §3 — Detecta se é um wrapper de LLM sem defensibilidade."""
    explicit_wrapper = len(profile.get("wrapper_indicators", [])) > 0
    low_moat = moat < 1.5
    wrapper_terms = ("openai", "langchain", "wrapper", "integração simples")
    text_combined = " ".join(profile.get("sinais_ai", [])).lower() + " " + \
                    " ".join(profile.get("wrapper_indicators", [])).lower()
    uses_llm_api = any(t in text_combined for t in wrapper_terms)
    no_custom = not profile.get("custom_model")
    no_proprietary = not profile.get("proprietary_data")

    if explicit_wrapper and low_moat and no_custom:
        return True
    if uses_llm_api and low_moat and no_custom and no_proprietary:
        return True
    if uses_llm_api and moat < 1.0 and "wrapper" in text_combined:
        return True
    return False


def _sector_score(profile: dict) -> float:
    """Setor estratégico para NVIDIA."""
    setor = (profile.get("setor") or "").lower()
    for keyword, weight in STRATEGIC_SECTORS.items():
        if keyword in setor:
            return weight
    return 0.4


def _tech_score(profile: dict) -> float:
    """Adoção atual de tech NVIDIA (sinais de uso).
    Extrai sinais NVIDIA de três fontes:
    1. sinais_ai (AI_SIGNALS matched no texto)
    2. stack (TECH_KEYWORDS matched)
    3. descricao (menções diretas de NVIDIA stack)
    """
    sinais = [s.lower() for s in profile.get("sinais_ai", [])]
    stack = [s.lower() for s in profile.get("stack", [])]
    desc = (profile.get("descricao") or "").lower()

    nvidia_signals = set(sinais) & {
        "cuda", "gpu", "tensorrt", "triton", "tts", "asr", "rag",
        "nvidia", "nemo", "clara", "monai", "isaac", "omniverse",
        "cudf", "cuml", "rapids", "riva", "nvidia nim",
    }

    nvidia_stack = set(stack) & {
        "cuda", "gpu", "tensorrt", "triton", "cudf", "cuml", "rapids",
        "monai", "clara", "nvidia nim", "riva", "isaac", "omniverse",
        "nemo guardrails", "nemo", "gpu cluster", "gpu computing",
    }

    nvidia_in_desc = set()
    for kw in ["cuda", "gpu", "tensorrt", "triton", "clara", "monai", "isaac", "rapids", "cuml", "riva", "nemo", "nvidia", "nvidia nim"]:
        if kw in desc:
            nvidia_in_desc.add(kw)

    nvidia_total = len(nvidia_signals) + len(nvidia_stack) * 0.5 + len(nvidia_in_desc) * 0.3
    return min(1.0, nvidia_total / 4.0)


def _traction_score(profile: dict) -> float:
    """Tração de mercado (sinais de growth/scale).
    Usa:
    1. tamanho_time (do perfil)
    2. descricao (keywords de tração)
    3. sinais_ai (sinais de scale)
    """
    score = 0.0

    desc = (profile.get("descricao") or "").lower()
    sinais = [s.lower() for s in profile.get("sinais_ai", [])]
    all_text = desc + " " + " ".join(sinais)

    if "milhões" in all_text or "milhares" in all_text or "mil" in all_text:
        score += 0.10
    if "1000+" in all_text or "10k+" in all_text or "100k+" in all_text or "1m+" in all_text or "5m+" in all_text or "50k+" in all_text or "20k+" in all_text or "20000" in all_text or "5.000" in all_text or "10.000" in all_text:
        score += 0.30
    if "clientes" in all_text or "customers" in all_text or "usuários" in all_text or "users" in all_text:
        score += 0.15
    if "b2b" in all_text or "enterprise" in all_text:
        score += 0.15
    if "crescimento" in all_text or "growth" in all_text or "tração" in all_text:
        score += 0.10
    if "investidores" in all_text or "rodada" in all_text:
        score += 0.10

    if profile.get("tamanho_time"):
        t = str(profile.get("tamanho_time", "")).lower()
        try:
            n = int(t)
            if n >= 1000:
                score += 0.40
            elif n >= 500:
                score += 0.30
            elif n >= 200:
                score += 0.20
            elif n >= 100:
                score += 0.10
            elif n >= 50:
                score += 0.05
        except (ValueError, TypeError):
            pass

    return min(1.0, score)


def _inception_fit_score(profile: dict, moat: float) -> tuple[float, dict]:
    """Score agregado de fit com Inception (0-1).

    Meta: ai_native >= 0.65, ai_enabled >= 0.45, wrapper < 0.30
    """
    moat_s = min(1.0, moat / 5.0) * 0.30
    tech_s = _tech_score(profile) * 0.30
    sector_s = _sector_score(profile) * 0.15
    traction_s = _traction_score(profile) * 0.20

    bonus = 0.0
    curated_cat = profile.get("categoria", "")
    if moat >= 2.0 and profile.get("custom_model"):
        bonus += 0.10
    if curated_cat == "ai_native" and moat >= 2.5:
        bonus += 0.05

    total = min(1.0, moat_s + tech_s + sector_s + traction_s + bonus)
    breakdown = {
        "moat": round(moat_s, 2),
        "tech": round(tech_s, 2),
        "sector": round(sector_s, 2),
        "traction": round(traction_s, 2),
    }
    return round(total, 2), breakdown


def classify(profile: dict) -> dict:
    """Rule-based classification. TAPI §5.1: 3 categorias apenas.

    Prioridade de categoria (CORRIGIDA após teste cego):
    1. Inferência por sinais do texto (moat + nativos/enabled + stack) — fonte primária
    2. curated_cat — usado APENAS para subir/baixar confiança, NUNCA para
       sobrescrever a categoria inferida. Isso garante que o classifier tem
       poder preditivo próprio e o curated_cat serve só como gabarito/reforço.

    O sinal de wrapper (_is_llm_wrapper) é calculado separadamente
    e NUNCA sobrescreve a categoria. Ele aparece como
    risco_wrapper=True no output para sinalizar o risco DENTRO
    da categoria que o perfil tem.
    """
    sinais = profile.get("sinais_ai", [])
    cases = profile.get("casos_uso", [])
    stack = profile.get("stack", [])
    desc = (profile.get("descricao") or "").lower()

    moat = _compute_moat(profile)
    is_wrapper = _is_llm_wrapper(profile, moat)
    fit, breakdown = _inception_fit_score(profile, moat)

    native_score = sum(1 for s in AI_NATIVE_SIGNALS if any(s in sig.lower() for sig in sinais))
    native_score += sum(1 for s in AI_NATIVE_SIGNALS if s in desc)
    enabled_score = sum(1 for s in AI_ENABLED_SIGNALS if any(s in sig.lower() for sig in sinais))
    enabled_score += sum(1 for s in AI_ENABLED_SIGNALS if s in desc)
    enabled_score += len(cases)

    # 1. Categoria SEMPRE inferida do texto primeiro
    # Regras empiricamente calibradas contra textos sintéticos fintech/retail:
    # - native_score >= 3 sozinha NÃO basta; moat é gatekeeper (moat >= 2.5)
    # - Fintechs/retail banks TÊM "bases de dados proprietários" por definição
    #   setorial, não por moat de AI-native — o gate de moat filtra isso
    # - non_ai requer: sem sinais_ai, sem cases, sem stack ML
    if native_score >= 3 and moat >= 2.5:
        categoria = "ai_native"
        confianca = min(0.95, 0.5 + native_score * 0.1 + moat * 0.05)
        just = f"AI-native com moat defensível ({moat:.1f}/5) — bom candidato para Inception."
    elif native_score >= 3 and moat >= 1.5:
        # native_score alto mas moat médio: ai_enabled com alto uso de AI
        categoria = "ai_enabled"
        confianca = min(0.9, 0.5 + enabled_score * 0.1)
        just = f"AI-enabled com alto score de AI ({native_score} sinais) mas moat moderado ({moat:.1f})."
    elif native_score >= 3 or any(s in desc for s in ["ai agent", "generative", "llm platform", "ai-native"]):
        categoria = "ai_enabled" if moat < 2.5 else "ai_native"
        if moat < 1.5:
            confianca = 0.50
            just = "Sinais de AI presentes mas sem moat claro."
        else:
            confianca = 0.70
            just = f"AI presente com moat moderado ({moat:.1f})."
    elif enabled_score >= 3 and (sinais or cases or stack):
        # enabled_score >= 3 só qualifies se há sinais de AI genuínos (não só stack genérico)
        # Isso evita que um stack Python+Docker + 1 sinal 'ia' vire ai_enabled
        categoria = "ai_enabled"
        confianca = min(0.9, 0.4 + enabled_score * 0.1)
        just = "AI augmenta o produto mas não é o core offering."
    elif enabled_score >= 2 and sinais:
        # Só ai_enabled se tem pelo menos sinais de AI genuínos
        categoria = "ai_enabled"
        confianca = 0.55
        just = "Uso limitado de AI para potencializar processo principal."
    else:
        categoria = "non_ai"
        confianca = 0.6
        just = "Não há sinais significativos de uso de IA."

    # 2. curated_cat entra SÓ como ajuste de confiança (não muda categoria)
    curated_cat = profile.get("categoria", "").lower()
    if curated_cat in ("ai_native", "ai_enabled", "non_ai"):
        if curated_cat == categoria:
            # Concordância: boost de confiança
            confianca = min(0.95, confianca + 0.10)
            just += " [concorda com curadoria]"
        else:
            # Discordância: marca como ponto de atenção, mas mantém a inferência
            confianca = max(0.4, confianca - 0.15)
            just += f" [divergente da curadoria: curadoria={curated_cat}]"

    return {
        "categoria": categoria,
        "confianca": round(confianca, 2),
        "justificativa": just,
        "evidencia_ai": sinais[:5],
        "moat_score": moat,
        "risco_wrapper": is_wrapper,
        "inception_fit_score": fit,
        "fit_breakdown": breakdown,
    }


async def classifier(state: AgentState) -> AgentState:
    """Classify startups with anti-wrapper + Inception fit."""
    profiles = state.extracted_profiles or []
    results = []
    n_wrapper = 0
    n_native = 0
    n_enabled = 0
    n_non = 0

    for profile in profiles:
        result = classify(profile)
        result["nome"] = profile["nome"]
        results.append(result)
        if result["risco_wrapper"]:
            n_wrapper += 1
        if result["categoria"] == "ai_native":
            n_native += 1
        elif result["categoria"] == "ai_enabled":
            n_enabled += 1
        else:
            n_non += 1

    state.classifications = results
    state.next_agent = "evidence_validator"
    logger.info(
        f"[classifier] {len(results)} startups — "
        f"ai_native={n_native} ai_enabled={n_enabled} "
        f"risco_wrapper={n_wrapper} non_ai={n_non}"
    )
    return state
