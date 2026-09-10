"""Agent 6: NVIDIA RAG Agent.

Queries the NVIDIA knowledge base via hybrid retrieval (dense + BM25)
with reranking. Returns most relevant technology references for the
identified gaps in each startup.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from agents.state import AgentState
from rag.retrieval.retriever import HybridRetriever


def build_rag_queries(profile: dict) -> list[str]:
    """Build RAG queries from a startup's profile and gaps."""
    queries = []

    gaps = profile.get("gaps_identificados", [])
    cases = profile.get("casos_uso", [])
    sinais = profile.get("sinais_ai", [])

    # Direct query: gaps and use cases
    if gaps:
        queries.append(" ".join(gaps[:3]))
    if cases:
        queries.append(" ".join(cases[:3]))

    # If LLM/AI signals, query for inference/serving
    if any(s in " ".join(sinais).lower() for s in ["llm", "gpt", "langchain", "rag"]):
        queries.append("LLM inference production deployment optimization")
    if any(s in " ".join(sinais).lower() for s in ["asr", "tts", "voice", "speech"]):
        queries.append("real-time speech AI")
    if any(s in " ".join(sinais).lower() for s in ["computer vision", "image"]):
        queries.append("computer vision inference optimization")

    # Sector-based
    setor = profile.get("setor", "").lower()
    if "fintech" in setor or "financeir" in setor:
        queries.append("fraud detection real-time inference")
    if "saúde" in setor or "health" in setor:
        queries.append("medical imaging AI HIPAA clinical")
    if "agr" in setor:
        queries.append("GPU accelerated data science agriculture")
    if "indústria" in setor or "iot" in setor:
        queries.append("predictive maintenance industrial AI")

    # Generic: startup program
    if not queries:
        queries.append("AI startup optimization NVIDIA Inception")

    return queries[:3]


def validate_citations(references: list[dict]) -> list[dict]:
    """Improvement #11 — citation validation.

    Checks that each reference chunk actually supports its claimed tech: the
    tech name (or a canonical alias) must appear in the chunk content/text.
    Drops/flag refs that fail the groundedness check so downstream
    recommendation doesn't cite unsupported technologies.
    """
    validity_by_tech = {
        "nvidia nim": "nim",
        "nvidia nemo": "nemo",
        "tensorrt-llm": "tensorrt",
        "tensorrt": "tensorrt",
        "triton": "triton",
        "rapids": "rapids",
        "cudf": "cudf",
        "cuml": "cuml",
        "morpheus": "morpheus",
        "clara": "clara",
        "monai": "monai",
        "riva": "riva",
        "omniverse": "omniverse",
        "isaac": "isaac",
        "jetpack": "jetpack",
        "jumpstart": "jumpstart",
        "inception": "inception",
        "guardrails": "guardrails",
        "ai enterprise": "ai enterprise",
    }

    for ref in references:
        tech = (ref.get("tech") or "").lower()
        content = ((ref.get("content") or "") + " " + (ref.get("title") or "")).lower()
        if not tech.strip():
            ref["valid"] = False
            continue
        key = next((k for k in validity_by_tech if k in tech), tech)
        if not key:
            ref["valid"] = False
            continue
        # Groundedness: keyword must surface in the chunk source text.
        # tech.split()[-1] é um alias seguro aqui porque key não é vazio.
        ref["valid"] = bool(
            key in content
            or any(alias in content for alias in (tech, tech.split()[-1]))
        )
    return references


async def nvidia_rag(state: AgentState) -> AgentState:
    """Query NVIDIA KB for relevant technology references.

    Se state.low_evidence=True (setado pelo grafo quando >50% das startups
    têm valido=False no evidence_results), pula a chamada ao RAG e emite
    referências mínimas, deixando o briefing sinalizar a evidência fraca.
    """
    profiles = state.extracted_profiles or []
    if not profiles:
        state.next_agent = "recommendation"
        return state

    if state.low_evidence:
        logger.warning(
            f"[nvidia_rag] low_evidence=True — pulando chamadas ao RAG "
            f"para {len(profiles)} startups"
        )
        state.nvidia_references = [
            {
                "nome": p["nome"],
                "references": [],
                "low_evidence": True,
            }
            for p in profiles
        ]
        for p in profiles:
            state.telemetry.evidence_reasons[p["nome"]] = "insufficient_evidence"
        state.next_agent = "recommendation"
        return state

    retriever = HybridRetriever()
    all_references = []

    # top_k de rerank ajustável: o supervisor pode ampliar via state.rag_top_k
    rag_top_k = max(int(getattr(state, "rag_top_k", 2) or 2), 1)

    async def _retrieve_with_retry(retriever, q: str, top_k: int = 2):
        """Tenta até 3 vezes com backoff 0s, 1s, 2s."""
        delays = [0, 1, 2]
        last_exc: Exception | None = None
        for attempt, delay in enumerate(delays, 1):
            if delay:
                await asyncio.sleep(delay)
            try:
                return await retriever.retrieve(q, top_k_rerank=top_k)
            except Exception as e:
                last_exc = e
                logger.warning(
                    f"[nvidia_rag] retrieve '{q[:40]}...' failed "
                    f"(attempt {attempt}/3): {e}"
                )
        raise last_exc  # type: ignore[misc]

    # Melhoria: consultas das startups rodam em paralelo (asyncio.gather), em
    # vez de sequenciais — reduz latência O(n) → ~O(ceil(n/concurrency)).
    rag_concurrency = max(int(getattr(state, "rag_concurrency", 3) or 1), 1)
    _sem = asyncio.Semaphore(rag_concurrency)

    async def _process_profile(profile: dict, retriever, top_k: int, sem) -> dict:
        async with sem:
            queries = build_rag_queries(profile)
            refs = []
            for q in queries:
                try:
                    results = await _retrieve_with_retry(retriever, q, top_k=top_k)
                    # Telemetry: rerank pre/post scores + effectiveness per (startup, query)
                    qkey = f"{profile['nome']}::{q[:60]}"
                    state.telemetry.retrieval_scores_pre_rerank[qkey] = \
                        list(getattr(retriever, "last_pre_rerank_scores", []) or [])
                    state.telemetry.retrieval_scores_post_rerank[qkey] = \
                        list(getattr(retriever, "last_post_rerank_scores", []) or [])
                    state.telemetry.rerank_effectiveness[qkey] = \
                        dict(getattr(retriever, "last_rerank_delta", {}) or {})
                    for r in results:
                        refs.append({
                            "tech": r["tech"],
                            "title": r["title"],
                            "content": r["content"],
                            "url": r["url"],
                            "score": r.get("rerank_score", 0),
                            "query": q,
                        })
                except Exception as e:
                    logger.debug(f"[nvidia_rag] Query '{q[:40]}' failed after retries: {e}")

            # Dedupe by tech, keep best score
            seen_techs = {}
            for ref in refs:
                tech = ref["tech"]
                if tech not in seen_techs or ref["score"] > seen_techs[tech]["score"]:
                    seen_techs[tech] = ref

            # Improvement #11: validate citations and drop unsupported techs
            validated = validate_citations(list(seen_techs.values()))
            valid_refs = [r for r in validated if r.get("valid", False)]
            retained = sorted(valid_refs, key=lambda x: -x["score"])[:5]

            invalid_refs = [r["tech"] for r in validated if not r.get("valid", False)]
            if invalid_refs:
                state.telemetry.evidence_reasons[profile["nome"]] = "groundedness"

            return {
                "nome": profile["nome"],
                "references": retained,
                "invalid_refs": invalid_refs,
            }

    all_references = list(await asyncio.gather(
        *[_process_profile(p, retriever, rag_top_k, _sem) for p in profiles]
    ))

    state.nvidia_references = all_references
    state.next_agent = "recommendation"
    logger.info(f"[nvidia_rag] Found references for {len(all_references)} startups")
    return state
