"""Retrieval evaluation metrics for the RAG pipeline.

Standard IR metrics computed against the golden set in `golden_set.py`:
- hit_rate@k: proportion of queries with at least one expected tech in top-k
- recall@k: average proportion of expected techs found in top-k
- mrr: mean reciprocal rank of the first expected tech
- precision@k: average proportion of top-k that are expected
"""
from __future__ import annotations

from collections.abc import Iterable


def _normalize(s: str) -> str:
    """Normaliza o texto para comparação (minúsculas e sem espaços)."""
    return (s or "").lower().strip()


def _tech_match(expected: str, retrieved_techs: list[str]) -> bool:
    """Check if expected tech appears in retrieved tech list.

    Uses case-insensitive substring matching to handle variants like
    "NVIDIA NIM" vs "NIM".
    """
    e = _normalize(expected)
    for t in retrieved_techs:
        nt = _normalize(t)
        if not nt:
            continue
        if e == nt or e in nt or nt in e:
            return True
    return False


def _rank_of_first(expected_list: list[str], retrieved_techs: list[str]) -> int | None:
    """Return 1-indexed position of the first expected tech in retrieved, or None."""
    for i, t in enumerate(retrieved_techs):
        for e in expected_list:
            nt = _normalize(t)
            ne = _normalize(e)
            if not nt:
                continue
            if ne == nt or ne in nt or nt in ne:
                return i + 1
    return None


def hit_rate_at_k(retrieved_per_query: list[list[str]], expected_per_query: list[list[str]], k: int) -> float:
    """% of queries with ≥1 expected tech in top-k."""
    if not retrieved_per_query:
        return 0.0
    hits = 0
    for retrieved, expected in zip(retrieved_per_query, expected_per_query, strict=True):
        top = retrieved[:k]
        if any(_tech_match(e, top) for e in expected):
            hits += 1
    return hits / len(retrieved_per_query)


def recall_at_k(retrieved_per_query: list[list[str]], expected_per_query: list[list[str]], k: int) -> float:
    """Average % of expected techs found in top-k."""
    if not retrieved_per_query:
        return 0.0
    total = 0.0
    for retrieved, expected in zip(retrieved_per_query, expected_per_query, strict=True):
        if not expected:
            continue
        top = retrieved[:k]
        found = sum(1 for e in expected if _tech_match(e, top))
        total += found / len(expected)
    return total / len(retrieved_per_query)


def precision_at_k(retrieved_per_query: list[list[str]], expected_per_query: list[list[str]], k: int) -> float:
    """Average % of top-k that are expected techs."""
    if not retrieved_per_query:
        return 0.0
    total = 0.0
    for retrieved, expected in zip(retrieved_per_query, expected_per_query, strict=True):
        top = retrieved[:k]
        if not top:
            continue
        hits = sum(1 for r in top if any(_tech_match(e, [r]) for e in expected))
        total += hits / len(top)
    return total / len(retrieved_per_query)


def mrr(retrieved_per_query: list[list[str]], expected_per_query: list[list[str]]) -> float:
    """Mean reciprocal rank of first expected tech."""
    if not retrieved_per_query:
        return 0.0
    total = 0.0
    for retrieved, expected in zip(retrieved_per_query, expected_per_query, strict=True):
        rank = _rank_of_first(expected, retrieved)
        if rank is not None:
            total += 1.0 / rank
    return total / len(retrieved_per_query)


def evaluate(
    retrieved_per_query: list[list[str]],
    expected_per_query: list[list[str]],
    k_values: Iterable[int] = (1, 3, 5, 10),
) -> dict:
    """Compute a panel of retrieval metrics.

    Args:
        retrieved_per_query: list of lists of retrieved tech names per query.
        expected_per_query: list of lists of expected tech names per query.
        k_values: cutoffs to report.

    Returns:
        dict of metric_name -> score (0..1).
    """
    results = {
        "mrr": mrr(retrieved_per_query, expected_per_query),
    }
    for k in k_values:
        results[f"hit_rate@{k}"] = hit_rate_at_k(retrieved_per_query, expected_per_query, k)
        results[f"recall@{k}"] = recall_at_k(retrieved_per_query, expected_per_query, k)
        results[f"precision@{k}"] = precision_at_k(retrieved_per_query, expected_per_query, k)
    return results
