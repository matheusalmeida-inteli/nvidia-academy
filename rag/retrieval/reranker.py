"""Rerankers — Cohere Rerank (production) + RerankFallback (offline / no API key).

The HybridRetriever uses `CohereRerank` when COHERE_API_KEY is set,
and falls back to `RerankFallback` otherwise.
"""
from __future__ import annotations

import os
from typing import Protocol

import numpy as np
from loguru import logger


class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 3
    ) -> list[dict]: ...


# Process-wide embedding cache (keyed by text) — the KB has only ~75 chunks,
# but the RAG node re-reranks them for every startup/query. Without this,
# each rerank re-encodes ~20 docs (~1.9s) and the pipeline takes ~85s.
_emb_call_cache: dict[str, np.ndarray] = {}


def _cached_embed(embedder, text: str) -> np.ndarray:
    vec = _emb_call_cache.get(text)
    if vec is None:
        vec = embedder.embed_batch([text])[0]
        _emb_call_cache[text] = vec
    return vec


class RerankFallback:
    """Local reranker: cosine similarity + keyword overlap.

    Used when Cohere Rerank is not available (no API key or offline).
    """

    def __init__(self, embedder) -> None:
        self.embedder = embedder

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 3
    ) -> list[dict]:
        """Reordena os documentos por cosseno + sobreposição de tokens."""
        if not documents:
            return []
        q_vec = _cached_embed(self.embedder, query)
        scored: list[dict] = []
        for doc in documents:
            content = doc.get("content", "")
            d_vec = _cached_embed(self.embedder, content[:500])
            n1, n2 = np.linalg.norm(q_vec), np.linalg.norm(d_vec)
            if n1 == 0 or n2 == 0:
                score = 0.0
            else:
                score = float(np.dot(q_vec, d_vec) / (n1 * n2))
            query_words = set(query.lower().split())
            doc_words = set(content.lower().split())
            overlap = (
                len(query_words & doc_words) / max(len(query_words), 1)
                if query_words
                else 0.0
            )
            final = 0.7 * score + 0.3 * overlap
            doc_copy = dict(doc)
            doc_copy["rerank_score"] = final
            doc_copy["rerank_source"] = "local_fallback"
            scored.append(doc_copy)
        scored.sort(key=lambda x: -x["rerank_score"])
        return scored[:top_k]


class CohereRerank:
    """Cohere Rerank (rerank-english-v3.0 / rerank-multilingual-v3.0).

    TAPI §5.3 names Cohere Rerank as the recommended reranker.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """Configura chave e modelo; o cliente é criado sob demanda (_ensure_client)."""
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.model = model or os.environ.get(
            "COHERE_RERANK_MODEL", "rerank-multilingual-v3.0"
        )
        self._client = None

    def is_available(self) -> bool:
        """Retorna True se há API key configurada."""
        return bool(self.api_key)

    def _ensure_client(self):
        """Cria o AsyncClient do Cohere sob demanda (lazy)."""
        if self._client is None:
            import cohere
            self._client = cohere.AsyncClient(api_key=self.api_key)
        return self._client

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 3
    ) -> list[dict]:
        """Chama a API Cohere Rerank e devolve os top_k documentos reordenados."""
        if not documents:
            return []
        if not self.is_available():
            raise RuntimeError("CohereRerank requires COHERE_API_KEY")

        try:
            client = self._ensure_client()
            contents = [
                d.get("content", "")[:4000] for d in documents
            ]
            response = await client.rerank(
                model=self.model,
                query=query,
                documents=contents,
                top_n=min(top_k, len(documents)),
                return_documents=False,
            )
        except Exception as e:
            logger.warning(f"Cohere rerank failed: {e}. Falling back to local.")
            raise

        ranked: list[dict] = []
        for r in response.results:
            doc = documents[r.index]
            doc_copy = dict(doc)
            doc_copy["rerank_score"] = float(r.relevance_score)
            doc_copy["rerank_source"] = "cohere"
            ranked.append(doc_copy)
        return ranked


class MMRReranker:
    """Maximal Marginal Relevance reranker — balances relevance & diversity.

    Wraps a base reranker (Cohere or local) and re-scores the results to
    avoid returning the same technology / topic repeatedly. Useful because
    the KB has many chunks per tech, so plain top-k can be dominated by a
    single tech.

    final_score = lambda * relevance - (1 - lambda) * max_similarity_to_selected
    """

    def __init__(self, base: Reranker, lambda_: float = 0.7) -> None:
        """Configura o reranker base e o peso (lambda) entre relevância e diversidade."""
        self.base = base
        self.lambda_ = lambda_

    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 3
    ) -> list[dict]:
        """Aplica MMR sobre o ranking base para diversificar os resultados."""
        if not documents:
            return []
        if top_k >= len(documents):
            return await self.base.rerank(query, documents, top_k=top_k)

        scored = await self.base.rerank(query, documents, top_k=len(documents))
        selected: list[dict] = []
        remaining = list(scored)

        while remaining and len(selected) < top_k:
            best_idx = None
            best_score = -float("inf")
            for i, cand in enumerate(remaining):
                relevance = cand.get("rerank_score") or cand.get("score") or 0.0
                # Similarity to already-selected items (max)
                diversity_penalty = 0.0
                if selected:
                    cand_text = (cand.get("content") or "")[:800].lower()
                    sims = []
                    for s in selected:
                        sel_text = (s.get("content") or "")[:800].lower()
                        sims.append(_text_jaccard(cand_text, sel_text))
                    diversity_penalty = max(sims) if sims else 0.0
                marg = self.lambda_ * relevance - (1 - self.lambda_) * diversity_penalty
                if marg > best_score:
                    best_score = marg
                    best_idx = i
            selected.append(remaining.pop(best_idx))
        return selected


def _text_jaccard(a: str, b: str) -> float:
    """Token Jaccard similarity between two texts."""
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)
