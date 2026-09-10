"""End-to-end evaluation: RAG retrieval -> citation validation -> recommendation.

Improvement #12.

This goes one step beyond rag/eval/run_eval.py: instead of only measuring
retrieval accuracy, it also validates that the citations are grounded
(tech name appears in the retrieved chunk) and that the final recommended
technologies are drawn *only* from validated references — mirroring the real
RAG->Recommendation flow in the multi-agent pipeline.

Metrics:
- retrieval_hit@k  : fraction of expected techs surfaced by retrieval
- citation_validity: fraction of recommended refs that pass grounding check
- recommendation_precision: fraction of recommended techs that are expected
- recommendation_recall    : fraction of expected techs that end up recommended
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from rag.eval.golden_set import EVAL_SAMPLES
from rag.retrieval.retriever import HybridRetriever


def _normalize(name: str) -> str:
    """Normaliza o nome da tecnologia (remove 'NVIDIA ', hífens e espaços)."""
    return name.lower().replace("nvidia ", "").replace("-", " ").strip()


def _matches(retrieved: str, expected: str) -> bool:
    """Verifica correspondência parcial entre tecnologia recuperada e esperada."""
    a, b = _normalize(retrieved), _normalize(expected)
    return a in b or b in a or a.split()[-1] in b or b.split()[-1] in a


async def _run_e2e(top_k: int = 3, out_path: Path | None = None) -> dict:
    """Executa a avaliação ponta a ponta (retrieval -> citação -> recomendação)."""
    retriever = HybridRetriever()
    rerank_name = type(retriever.reranker).__name__

    per_query = []
    total_retr_hits = 0
    total_expected = 0
    total_valid_cites = 0
    total_cites = 0
    total_rec_prec = 0.0
    total_rec_recall = 0.0

    for sample in EVAL_SAMPLES:
        expected = sample["techs_esperadas"]
        total_expected += len(expected)

        results = await retriever.retrieve(sample["query"], top_k_rerank=top_k)

        # Distinct techs surfaced by retrieval (top_k)
        retrieved_techs = []
        seen = set()
        for r in results:
            t = r.get("tech", "")
            if t and t not in seen:
                seen.add(t)
                retrieved_techs.append(t)

        # Retrieval hit@k
        retr_hits = [
            e for e in expected
            if any(_matches(r, e) for r in retrieved_techs)
        ]
        total_retr_hits += len(retr_hits)

        # Citation validation (groundedness) on the recommended refs
        valid_cites = 0
        for r in results:
            content = ((r.get("content") or "") + " " + (r.get("title") or "")).lower()
            tech = (r.get("tech") or "").lower()
            grounded = bool(tech and (tech in _normalize(content)
                                      or tech.split()[-1] in content))
            if grounded:
                valid_cites += 1
        total_cites += len(results)
        total_valid_cites += valid_cites

        # Recommendation = validated, distinct techs (grounded only)
        recommended = []
        seen_rec = set()
        for r in results:
            content = ((r.get("content") or "") + " " + (r.get("title") or "")).lower()
            tech = (r.get("tech") or "").lower()
            grounded = bool(tech and (tech in _normalize(content)
                                      or tech.split()[-1] in content))
            if grounded and tech not in seen_rec:
                seen_rec.add(tech)
                recommended.append(r.get("tech"))

        rec_hits = [e for e in expected if any(_matches(r, e) for r in recommended)]
        prec = len(rec_hits) / len(recommended) if recommended else 0.0
        rec = len(rec_hits) / len(expected) if expected else 0.0
        total_rec_prec += prec
        total_rec_recall += rec

        per_query.append({
            "id": sample["id"],
            "query": sample["query"],
            "retrieved_techs": retrieved_techs,
            "recommended_techs": recommended,
            "expected": expected,
            "retrieval_hits": retr_hits,
            "recommendation_hits": rec_hits,
            "citation_validity": round(valid_cites / len(results), 2) if results else 0.0,
        })

    n = len(EVAL_SAMPLES)
    metrics = {
        "retrieval_hit_at_k": round(total_retr_hits / max(total_expected, 1), 3),
        "citation_validity_rate": round(total_valid_cites / max(total_cites, 1), 3),
        "recommendation_precision": round(total_rec_prec / n, 3),
        "recommendation_recall": round(total_rec_recall / n, 3),
    }

    print("\n=== END-TO-END EVAL (RAG -> Recommendation) ===")
    print(f"  reranker        : {rerank_name}")
    print(f"  samples         : {n}")
    print(f"  top_k           : {top_k}")
    for k, v in metrics.items():
        print(f"  {k:<26} {v:.3f}")

    report = {
        "reranker": rerank_name,
        "n_samples": n,
        "top_k": top_k,
        "metrics": metrics,
        "per_query": per_query,
    }

    if out_path:
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport written to: {out_path}")

    return report


def main() -> None:
    """CLI da avaliação ponta a ponta (--top-k e --json)."""
    parser = argparse.ArgumentParser(description="Run end-to-end RAG->Recommendation eval")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()
    out = Path(args.json) if args.json else None
    asyncio.run(_run_e2e(args.top_k, out))


if __name__ == "__main__":
    main()
