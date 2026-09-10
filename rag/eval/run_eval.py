"""Run RAG evaluation against the golden set.

Usage:
    python -m rag.eval.run_eval                # default settings
    python -m rag.eval.run_eval --top-k 5      # custom retrieval top-k
    python -m rag.eval.run_eval --json out.json  # write report to JSON
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from loguru import logger

from rag.eval.golden_set import EVAL_SAMPLES
from rag.eval.metrics import evaluate
from rag.retrieval.retriever import HybridRetriever


async def _run_evaluation(top_k: int, out_path: Path | None, no_rerank: bool = False) -> dict:
    """Executa a avaliação RAG sobre o golden set e retorna o relatório agregado."""
    # A/B: RAG_RERANK=0 disables reranking to measure quality vs cost.
    os.environ["RAG_RERANK"] = "0" if no_rerank else "1"

    print("=" * 70)
    print("RAG EVALUATION — NVIDIA Startup AI Radar")
    print("=" * 70)
    print(f"\nGolden set: {len(EVAL_SAMPLES)} samples")
    print(f"Retrieval top_k (rerank): {top_k}")
    if no_rerank:
        print("RERANKING: DISABLED (RAG_RERANK=0)")
    print()

    retriever = HybridRetriever()
    if isinstance(retriever.reranker, type(retriever.reranker)):
        rerank_name = type(retriever.reranker).__name__
    else:
        rerank_name = "?"
    print(f"Reranker: {rerank_name}")
    print()

    retrieved_per_query: list[list[str]] = []
    expected_per_query: list[list[str]] = []
    per_query_records = []
    latencies = []
    stage_acc: dict[str, float] = {}
    stage_count: dict[str, int] = {}
    delta_acc = {"reorder_fraction": [], "kendall_tau": []}

    for sample in EVAL_SAMPLES:
        q = sample["query"]
        expected = sample["techs_esperadas"]
        expected_per_query.append(expected)
        t0 = time.perf_counter()
        try:
            results = await retriever.retrieve(q, top_k_rerank=top_k)
        except Exception as e:
            logger.error(f"Query {sample['id']} failed: {e}")
            results = []
        latencies.append(time.perf_counter() - t0)

        # Accumulate stage timings for aggregate breakdown
        for stage, ms in getattr(retriever, "last_stage_times", {}).items():
            stage_acc[stage] = stage_acc.get(stage, 0) + ms
            stage_count[stage] = stage_count.get(stage, 0) + 1

        # Accumulate rerank effectiveness deltas
        rdelta = getattr(retriever, "last_rerank_delta", {}) or {}
        if rdelta:
            delta_acc["reorder_fraction"].append(rdelta.get("reorder_fraction", 0.0))
            delta_acc["kendall_tau"].append(rdelta.get("kendall_tau", 0.0))

        retrieved_techs = []
        seen = set()
        for r in results:
            t = r.get("tech", "")
            if t and t not in seen:
                seen.add(t)
                retrieved_techs.append(t)
        retrieved_per_query.append(retrieved_techs)

        hits = [t for t in retrieved_techs if any(
            t.lower() in e.lower() or e.lower() in t.lower() for e in expected
        )]
        per_query_records.append({
            "id": sample["id"],
            "query": q,
            "expected": expected,
            "retrieved": retrieved_techs,
            "hits": hits,
            "latency_ms": round(latencies[-1] * 1000, 1),
            "stage_ms": {k: round(v, 1) for k, v in getattr(retriever, "last_stage_times", {}).items()},
            "rerank_delta": getattr(retriever, "last_rerank_delta", {}),
        })

        marker = "✓" if hits else "✗"
        print(f"  {marker} [{sample['id']}] {q[:50]:<50}")
        print(f"      expected: {expected}")
        print(f"      got:      {retrieved_techs[:top_k]}")
        print(f"      hits:     {hits}  ({latencies[-1] * 1000:.0f}ms)")
        print()

    metrics = evaluate(retrieved_per_query, expected_per_query, k_values=(1, 3, 5))

    print("=" * 70)
    print("AGGREGATE METRICS")
    print("=" * 70)
    for name, score in metrics.items():
        print(f"  {name:<20} {score:.3f}  ({score * 100:.1f}%)")
    if latencies:
        avg_ms = sum(latencies) / len(latencies) * 1000
        p95_ms = sorted(latencies)[int(len(latencies) * 0.95)] * 1000
        print(f"  {'latency_avg_ms':<20} {avg_ms:.1f}")
        print(f"  {'latency_p95_ms':<20} {p95_ms:.1f}")

    # Aggregate stage breakdown
    stage_breakdown = {}
    if stage_count:
        print("\n  STAGE BREAKDOWN (avg ms):")
        for stage, total in sorted(stage_acc.items()):
            avg = total / stage_count[stage]
            stage_breakdown[stage] = round(avg, 1)
            print(f"    {stage:<20} {avg:.1f}ms")

    # Aggregate rerank effectiveness delta
    rerank_effectiveness_avg = {}
    if no_rerank:
        print("\n  RERANK EFFECTIVENESS: n/a (reranking disabled)")
    elif delta_acc["reorder_fraction"]:
        rerank_effectiveness_avg = {
            "avg_reorder_fraction": round(sum(delta_acc["reorder_fraction"]) / len(delta_acc["reorder_fraction"]), 4),
            "avg_kendall_tau": round(sum(delta_acc["kendall_tau"]) / len(delta_acc["kendall_tau"]), 4),
            "n_queries": len(delta_acc["reorder_fraction"]),
        }
        print("\n  RERANK EFFECTIVENESS (avg):")
        print(f"    reorder_fraction: {rerank_effectiveness_avg['avg_reorder_fraction']}")
        print(f"    kendall_tau:      {rerank_effectiveness_avg['avg_kendall_tau']}")

    report = {
        "reranker": rerank_name if not no_rerank else "disabled",
        "n_samples": len(EVAL_SAMPLES),
        "top_k": top_k,
        "metrics": metrics,
        "latency_avg_ms": round(sum(latencies) / len(latencies) * 1000, 1) if latencies else 0,
        "latency_p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 1) if latencies else 0,
        "stage_breakdown_ms": stage_breakdown,
        "rerank_effectiveness_avg": rerank_effectiveness_avg,
        "per_query": per_query_records,
    }

    if out_path:
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport written to: {out_path}")

    return report


def main() -> None:
    """CLI da avaliação: --top-k, --json e --no-rerank (A/B)."""
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--top-k", type=int, default=3, help="Retrieval top-k")
    parser.add_argument("--json", type=str, default=None, help="Write report to JSON file")
    parser.add_argument("--no-rerank", action="store_true", help="Disable reranking (A/B quality vs cost)")
    args = parser.parse_args()
    out = Path(args.json) if args.json else None
    asyncio.run(_run_evaluation(args.top_k, out, no_rerank=args.no_rerank))


if __name__ == "__main__":
    main()
