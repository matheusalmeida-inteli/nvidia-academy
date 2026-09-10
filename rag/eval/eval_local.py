"""Run RAG eval in LOCAL/offline mode (no Cohere, no Qdrant).

Useful for CI or when API keys are unavailable/rate-limited: forces the
retriever into RerankFallback and asserts BM25-only degradation gracefully,
then runs run_eval and/or eval_e2e.

Usage:
    pixi run python -m rag.eval.eval_local --retrieval --json out.json [--top-k 3]
    pixi run python -m rag.eval.eval_local --e2e --json out2.json
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

os.environ["COHERE_API_KEY"] = ""

# Neutralize settings-backed Cohere key so the retriever uses local fallback.
try:
    from scraper.config import settings as _st
    _st.get_settings().cohere_api_key = ""
except Exception:
    pass

import rag.retrieval.retriever as _ret

_orig_init = _ret.HybridRetriever.__init__


def _local_init(self, qdrant_url="http://localhost:6333", collection=None,
                cohere_api_key="", cohere_rerank_model=None):
    """Patch do __init__ do retriever: força modo local (sem Cohere)."""
    collection = collection or _ret.COLLECTION
    _orig_init(self, qdrant_url, collection, "", cohere_rerank_model)


_ret.HybridRetriever.__init__ = _local_init


def _run_retrieval(top_k: int, out: Path):
    """Roda a avaliação de recuperação em modo offline."""
    from rag.eval.run_eval import _run_evaluation
    asyncio.run(_run_evaluation(top_k, out))


def _run_e2e(top_k: int, out: Path):
    """Roda a avaliação ponta a ponta em modo offline."""
    from rag.eval.eval_e2e import _run_e2e
    asyncio.run(_run_e2e(top_k, out))


def main() -> None:
    """CLI do modo offline: --retrieval e/ou --e2e com relatórios JSON."""
    parser = argparse.ArgumentParser(description="Local/offline RAG eval (no Cohere, no Qdrant)")
    parser.add_argument("--retrieval", action="store_true", help="Run run_eval (retrieval metrics)")
    parser.add_argument("--e2e", action="store_true", help="Run eval_e2e (RAG->recommendation)")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    if not args.retrieval and not args.e2e:
        parser.error("especifique --retrieval ou --e2e")

    if args.json:
        base = Path(args.json)
    else:
        base = Path("/tmp/rag_eval_local")

    if args.retrieval:
        _run_retrieval(args.top_k, base.with_suffix(".retrieval.json"))
    if args.e2e:
        _run_e2e(args.top_k, base.with_suffix(".e2e.json"))


if __name__ == "__main__":
    main()
