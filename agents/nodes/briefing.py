"""Agent 8: Briefing Agent.

TAPI §2(6) — Gera briefing executivo em 3 ângulos:
- Comercial
- Técnico
- Comunitário

E para o gerente de Startups & VCs da NVIDIA atrair/qualificar/nutrir:
- inception_fit_score
- wrapper_warning
- nurture_suggestion
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loguru import logger

from agents.state import AgentState, Briefing, Recommendation


def _cadence_for(estagio: str) -> str:
    """Define a cadência de nutrição (quinzenal/mensal) conforme o estágio."""
    if not estagio:
        return "mensal"
    s = estagio.lower()
    if "pre-seed" in s or "pre_seed" in s:
        return "quinzenal"
    if "seed" in s:
        return "quinzenal"
    if "serie_a" in s or "série a" in s:
        return "mensal"
    if "serie_b" in s or "série b" in s:
        return "mensal"
    if "serie_c" in s or "série c" in s:
        return "mensal"
    return "mensal"


def _next_action_date_for(cadence: str) -> str:
    """Calcula a data da próxima ação de nutrição (ISO) a partir da cadência."""
    today = datetime.now(UTC).date()
    if cadence == "semanal":
        d = today + timedelta(days=7)
    elif cadence == "quinzenal":
        d = today + timedelta(days=14)
    elif cadence == "mensal":
        d = today + timedelta(days=28)
    else:
        d = today + timedelta(days=60)
    return d.isoformat()


def build_briefing(state: AgentState) -> Briefing:
    """Construção do briefing executivo a partir do estado final do grafo.

    Seleciona a startup de melhor fit, monta as Recommendation dataclasses,
    gera os próximos passos nos três ângulos (comercial, técnico, comunitário)
    e a sugestão de nutrição (TAPI §2.6). Sem recomendações, devolve briefing
    informativo com sugestões de refinamento de query.

    IMPROVEMENT: agora considera a relevância da `user_query` ao selecionar a
    startup alvo, evitando que o briefing seja gerado para a primeira startup
    do estado sem conexão com a intenção do usuário.
    """
    recommendations = state.recommendations or []
    if not recommendations:
        # No startups matched - return meaningful empty briefing
        return Briefing(
            empresa="(Nenhuma startup encontrada)",
            setor="—",
            maturidade_ai="—",
            score_maturidade=0.0,
            recomendacoes=[],
            proximos_comerciais=["Tente refinar a query com setor/estágio específico"],
            proximos_tecnicos=["Revisar keywords de busca no RAG"],
            proximos_comunitarios=[],
            inception_fit_score=0.0,
            wrapper_warning=False,
            fit_breakdown={},
            nurture_suggestion="Sem startups para nutrir; revisar estratégia de query.",
            fontes_consultadas=[],
            generated_at=datetime.now(UTC).isoformat(),
        )

    # --- Calcular relevância da query para cada startup ---
    def _relevance_score(profile: dict, user_query: str) -> float:
        """Conta quantas keywords da query aparecem no perfil da startup."""
        if not user_query:
            return 0.0
        q = user_query.lower()
        # Texto do perfil: nome + setor + sinais_ai + gaps_identificados + casos_uso
        profile_text = " "
        profile_text += (profile.get("nome") or "") + " "
        profile_text += (profile.get("setor") or "") + " "
        profile_text += " ".join(profile.get("sinais_ai") or []) + " "
        profile_text += " ".join(profile.get("gaps_identificados") or []) + " "
        profile_text += " ".join(profile.get("casos_uso") or [])
        # Token simple: palavras com 3+ chars
        tokens = [t for t in q.split() if len(t) >= 3]
        if not tokens:
            return 0.0
        score = sum(1 for t in tokens if t in profile_text.lower())
        return score / max(len(tokens), 1)

    # --- Função de ordenação: relevance × fit, tiebreak por confiança ---
    def _top_key(r: dict) -> tuple:
        """Chave de ordenação: relevance × fit score, confiança, ausência de wrapper."""
        # Associa o profile da startup ao recommendation
        nome = r.get("nome", "")
        profile = next(
            (p for p in state.extracted_profiles if p.get("nome") == nome), {}
        )
        rel = _relevance_score(profile, state.user_query or "")
        fit = r.get("inception_fit_score", 0.0)
        conf = r.get("confianca", 0.0)
        wrapper = 0 if r.get("risco_wrapper") else 1
        # relevance × fit garante que a startup mais relevante para a query
        # também tenha bom fit Inception; confiança quebra o empate
        return (rel * fit, fit, conf, wrapper)

    top = max(recommendations, key=_top_key)
    empresa = top.get("nome", "N/A")

    # Transparência da escolha (anti-"startup aleatória"): mostra por quê.
    _p_sel = next(
        (p for p in state.extracted_profiles if p.get("nome") == empresa), {}
    )
    _rel_sel = _relevance_score(_p_sel, state.user_query or "")
    _fit_sel = top.get("inception_fit_score", 0.0)
    criterio_selecao = (
        f"Selecionada por melhor fit × relevância à consulta "
        f"(fit {_fit_sel:.0%}, relevância {_rel_sel:.2f}, score {_fit_sel * _rel_sel:.3f})"
    )

    profile = next(
        (p for p in state.extracted_profiles if p.get("nome") == empresa), {}
    )
    classif = next(
        (c for c in state.classifications if c.get("nome") == empresa), {}
    )
    evidence = next(
        (e for e in state.evidence_results if e.get("nome") == empresa), {}
    )

    # Constrói Recommendation dataclasses
    recs = []
    for r in top.get("recomendacoes", []):
        recs.append(Recommendation(
            tecnologia=r.get("tecnologia", ""),
            justificativa_tecnica=r.get("justificativa_tecnica", ""),
            justificativa_negocio=r.get("justificativa_negocio", ""),
            prioridade=r.get("prioridade", "medium"),
            complexidade=r.get("complexidade", "medium"),
            proxima_acao=r.get("proxima_acao", ""),
            evidencias=r.get("evidencias", []),
            fontes_rag=r.get("fontes_rag", []),
        ))

    # ---- Fontes RAG consolidadas (TAPI §5.3 rastreabilidade) ----
    fontes_rag_all: list[dict] = []
    for r in recs:
        for f in r.fontes_rag:
            if f and f not in fontes_rag_all:
                fontes_rag_all.append(f)

    # ---- Próximos passos em 3 ângulos (TAPI §2.6) ----
    community_actions = top.get("community_actions", [])
    proximos_comerciais: list[str] = []
    proximos_tecnicos: list[str] = []
    proximos_comunitarios: list[str] = []

    # Comerciais
    high_recs = [r for r in recs if r.prioridade == "high"]
    if high_recs:
        # Ação comercial alinhada à melhor tech — usa a proxima_acao já
        # contextualizada por origem/regra (não é placeholder genérico).
        top = high_recs[0]
        proximos_comerciais.append(
            f"Agendar reunião de descoberta com foco em {top.tecnologia}: "
            f"{top.proxima_acao.lower()}"
        )
    if classif.get("categoria") in ("ai_native", "ai_enabled"):
        fit = classif.get("inception_fit_score", 0)
        gaps = profile.get("gaps_identificados") or []
        foco = f" — foco em {gaps[0]}" if gaps else ""
        if fit >= 0.65:
            proximos_comerciais.append(
                f"Apresentar proposta formal de NVIDIA Inception (fit score {fit:.0%}{foco})"
            )
        elif fit >= 0.4:
            proximos_comerciais.append(
                "Apresentar NVIDIA Inception como exploração — fit moderado, "
                f"coletar mais sinais{foco}"
            )
        else:
            proximos_comerciais.append(
                "Adiar abordagem comercial; investir primeiro em educação/engajamento"
            )
    if classif.get("risco_wrapper"):
        proximos_comerciais.append(
            "Conversa exploratória: ajudar a construir defensibilidade antes de pitch comercial"
        )
    if profile.get("gaps_identificados"):
        gap_target = profile.get("gaps_identificados", [])[0]
        tech_direct = next((r.tecnologia for r in high_recs), None)
        if tech_direct:
            proximos_comerciais.append(
                f"Ancorar ROI em {gap_target}: propor {tech_direct} como resolvê-lo "
                f"em 90 dias com metas mensuráveis"
            )
    if not proximos_comerciais:
        proximos_comerciais.append("Manter em nutrição passiva; revisar em 60 dias")

    # Técnicos
    for r in high_recs[:2]:
        if r.tecnologia in ("NVIDIA NIM", "Triton", "TensorRT-LLM"):
            proximos_tecnicos.append(
                f"Propor POC técnica com {r.tecnologia} — benchmark de latência/custo"
            )
        elif r.tecnologia in ("RAPIDS", "cuDF", "cuML"):
            proximos_tecnicos.append(
                f"Workshop técnico de {r.tecnologia} — 2h hands-on com time da startup"
            )
        elif r.tecnologia == "NeMo Guardrails":
            proximos_tecnicos.append(
                "POC de safety/governance para agentes de IA — protótipo 1-2 semanas"
            )
        elif r.tecnologia == "Riva":
            proximos_tecnicos.append(
                "POC de ASR/TTS em Português Brasileiro — medir WER vs solução atual"
            )
        else:
            proximos_tecnicos.append(
                f"Sessão técnica sobre {r.tecnologia} com NVIDIA Solution Architect"
            )
    if evidence.get("lacunas"):
        proximos_tecnicos.append(
            "Coletar evidências técnicas adicionais: métricas de inferência, "
            "volume de requests, modelo de custo"
        )
    if not proximos_tecnicos:
        proximos_tecnicos.append("Sessão técnica geral sobre NVIDIA AI stack")

    if getattr(state, "low_evidence", False):
        proximos_tecnicos.insert(
            0,
            "⚠️ Evidência insuficiente — recomendações geradas com base em sinais "
            "parciais; coletar métricas técnicas (latência, volume, custo) antes "
            "de comprometer POCs"
        )

    # Comunitários
    proximos_comunitarios = list(community_actions) if community_actions else [
        "Convite para próximo NVIDIA meetup Brasil (SP ou RJ)",
        "Newsletter mensal NVIDIA Inception",
    ]

    # Fontes
    fontes = []
    for e in evidence.get("evidencias", []):
        if e.get("url"):
            fontes.append(e["url"])

    # Nutrição
    estagio = profile.get("estagio", "")
    cadence = _cadence_for(estagio)
    next_date = _next_action_date_for(cadence)
    if classif.get("risco_wrapper"):
        nurture_suggestion = (
            f"⚠️ Wrapper LLM. Cadência {cadence} focada em educação. "
            f"Próxima ação: {proximos_comunitarios[0] if proximos_comunitarios else 'workshop'}"
        )
    elif classif.get("inception_fit_score", 0) >= 0.65:
        nurture_suggestion = (
            f"Alto fit Inception ({classif.get('inception_fit_score', 0):.0%}). "
            f"Cadência {cadence} com mix técnico + comercial. "
            f"Próxima ação em {next_date}."
        )
    else:
        nurture_suggestion = (
            f"Fit moderado. Cadência {cadence}, foco em construir sinais de moat. "
            f"Próxima ação em {next_date}."
        )

    return Briefing(
        empresa=empresa,
        setor=profile.get("setor", "N/A"),
        maturidade_ai=classif.get("categoria", "N/A"),
        score_maturidade=classif.get("confianca", 0.0),
        recomendacoes=recs,
        proximos_comerciais=proximos_comerciais,
        proximos_tecnicos=proximos_tecnicos,
        proximos_comunitarios=proximos_comunitarios,
        inception_fit_score=classif.get("inception_fit_score", 0.0),
        wrapper_warning=classif.get("risco_wrapper", False),
        fit_breakdown=classif.get("fit_breakdown", {}),
        criterio_selecao=criterio_selecao,
        nurture_suggestion=nurture_suggestion,
        fontes_consultadas=fontes,
        fontes_rag=fontes_rag_all,
        generated_at=datetime.now(UTC).isoformat(),
        evidencia_insuficiente=getattr(state, "low_evidence", False),
    )


async def briefing(state: AgentState) -> AgentState:
    """Generate final executive briefing (3 ângulos)."""
    state.briefing = build_briefing(state)
    state.next_agent = "__end__"
    logger.info(f"[briefing] Generated briefing for: {state.briefing.empresa}")
    return state
