"""Hybrid retrieval with reranking.

Combines dense (Qdrant vector) + sparse (BM25) search, then reranks
top-k results using Cohere Rerank (when COHERE_API_KEY is set) or a
local semantic fallback otherwise.
"""
from __future__ import annotations

import asyncio
import os

import numpy as np
from loguru import logger
from qdrant_client import AsyncQdrantClient

from rag.config import (
    category_boost,
    local_dense_fallback,
    mmr_enabled,
    mmr_lambda,
    query_rewrite_enabled,
    rerank_enabled,
    rrf_cap,
    rrf_dense_weight,
    rrf_k,
    rrf_sparse_weight,
)
from rag.ingest.embeddings import CohereEmbedder
from rag.ingest.ingestor import BM25, COLLECTION
from rag.ingest.shared import get_chunked_meta, get_chunked_texts
from rag.retrieval.reranker import CohereRerank, Reranker, RerankFallback

# Corpus embedding cache for the local dense fallback (no Qdrant needed).
# Keyed by a hash of the corpus texts so a corpus change invalidates it.
_CORPUS_EMBEDDING_CACHE: dict[str, list[np.ndarray]] = {}

# In-process cache of successful retrieve() calls, so repeated RAG queries
# (demo re-runs, duplicate query strings across startups, retries) skip the
# Cohere embed + Qdrant + Cohere rerank roundtrips that spike latency.
# Key: (query, top_k_dense, top_k_sparse, top_k_rerank).
_RETRIEVE_CACHE: dict[tuple, dict] = {}


# Nomes canônicos de techs NVIDIA: variações ("NVIDIA RAPIDS" vs "RAPIDS",
# "NVIDIA Triton Inference Server" vs "Triton", "NVIDIA AI Enterprise" vs
# "AI Enterprise") colapsam para um único bucket de RRF/dedup.
_CANONICAL_ALIASES: dict[str, str] = {
    "NVIDIA Morpheus": "Morpheus",
    "NVIDIA Clara": "Clara",
    "NVIDIA NIM": "NVIDIA NIM",
    "NVIDIA AI Enterprise": "AI Enterprise",
    "NVIDIA Triton Inference Server": "Triton",
    "NVIDIA Triton": "Triton",
    "NVIDIA Isaac": "Isaac",
    "NVIDIA Riva": "Riva",
    "NVIDIA MONAI": "MONAI",
    "NVIDIA AI Services": "AI Services",
    "NVIDIA Omniverse": "Omniverse",
    "NVIDIA NeMo": "NeMo",
    "NVIDIA RAPIDS": "RAPIDS",
}


def _canonical_tech(tech: str) -> str:
    """Normaliza o nome de tecnologia para o canônico usado em fusão/dedup."""
    return _CANONICAL_ALIASES.get(tech or "", tech or "")


def _corpus_cache_key(texts: list[str]) -> str:
    return str(abs(hash("\\n".join(texts))))


# Taxonomy for query expansion — maps domain concepts to related terms so that
# short / natural-language queries reach the right KB chunks.
QUERY_EXPANSIONS: dict[str, list[str]] = {
    "llm": ["llm", "inference", "serving", "deployment", "generative"],
    "inference": ["inference", "serving", "triton", "nim", "tensorrt"],
    "serving": ["serving", "triton", "inference", "deployment", "kubernetes"],
    "fraud": ["fraud", "morpheus", "rapids", "cuml", "anomaly", "threat"],
    "speech": ["speech", "riva", "asr", "tts", "voice", "portuguese"],
    "voice": ["voice", "riva", "asr", "tts", "speech"],
    "medical": ["medical", "clara", "monai", "imaging", "healthcare", "diagnosis"],
    "health": ["health", "healthcare", "clara", "monai", "medical"],
    "imaging": ["imaging", "clara", "monai", "medical"],
    "robotics": ["robotics", "isaac", "omniverse", "simulation", "jetson"],
    "simulation": ["simulation", "omniverse", "isaac", "digital twin"],
    "data science": ["data science", "rapids", "cudf", "cuml", "gpu"],
    "cybersecurity": ["cybersecurity", "morpheus", "anomaly", "threat"],
    "cyber": ["cybersecurity", "morpheus", "anomaly", "threat"],
    "guardrails": ["guardrails", "nemo guardrails", "safety", "governance"],
    "safety": ["safety", "guardrails", "nemo guardrails"],
    "governance": ["governance", "guardrails", "compliance"],
    "custom model": ["custom model", "nemo", "fine-tuning", "rlhf"],
    "fine-tuning": ["fine-tuning", "nemo", "rlhf", "llm", "customization"],
    "agriculture": ["agriculture", "agtech", "rapids", "isaac", "precision"],
    "agro": ["agro", "agriculture", "agtech", "rapids", "isaac"],
    "retail": ["retail", "rapids", "cudf", "recommendation", "forecasting"],
    "fintech": ["fintech", "fraud", "nim", "morpheus", "credit"],
    "enterprise": ["enterprise", "ai enterprise", "triton", "compliance"],
    "generative": ["generative", "nim", "omniverse", "image", "video"],
}


def expand_query(query: str) -> str:
    """Expand a query with domain-related terms to improve recall.

    Appends matching taxonomy keywords to the original query while keeping
    the original intent intact. Used for both dense embedding and BM25.
    """
    q = query.lower()
    extra: list[str] = []
    for key, terms in QUERY_EXPANSIONS.items():
        if key in q:
            for t in terms:
                if t not in extra:
                    extra.append(t)
    if not extra:
        return query
    return query + " " + " ".join(extra)


async def rewrite_query_with_llm(query: str) -> str:
    """Rewrite a natural-language query with the LLM (improvement #9).

    Only active when RAG_QUERY_REWRITE=1 and an LLM backend is configured.
    Rewrites the user's query into a retrieval-friendly form. Falls back to the
    original query if the LLM is unavailable or the call fails.
    """
    if not query_rewrite_enabled():
        return query
    try:
        from agents.llm import llm
        if not llm.is_available():
            return query
        system = (
            "You rewrite a startup's natural-language query into a concise, "
            "retrieval-optimized search query for an NVIDIA AI tech KB. "
            "Keep domain terms; return ONLY the rewritten query, no quotes."
        )
        user = f"Revise: {query}"
        rewritten = await llm.complete(system, user, temperature=0.2, max_tokens=120)
        rewritten = rewritten.strip().strip('"').strip()
        if rewritten and len(rewritten) < 200:
            logger.info(f"Query rewritten: '{query}' -> '{rewritten}'")
            return rewritten
    except Exception as e:
        logger.warning(f"Query rewrite failed; using original ({e})")
    return query


class HybridRetriever:
    """Retriever híbrido (dense Qdrant + BM25) com RRF e reranking configurável."""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection: str = COLLECTION,
        cohere_api_key: str | None = None,
        cohere_rerank_model: str | None = None,
    ) -> None:
        """Conecta Qdrant, carrega/fitta o BM25 (com cache) e escolhe o reranker."""
        self.qdrant = AsyncQdrantClient(url=qdrant_url)
        self.collection = collection
        self.embedder = CohereEmbedder()
        # Dimensão real da collection (cacheada após o primeiro get_collection).
        # 0 = desconhecida (Qdrant indisponível). Usada p/ escolher o embedder de
        # consulta coerente com o que foi persistido na ingestão.
        self._collection_dim: int | None = None
        # Use cached BM25 index when the corpus hash matches, else fit + cache
        from rag.retrieval.bm25_cache import load_cached_bm25, save_cached_bm25
        texts = get_chunked_texts()
        self.bm25 = load_cached_bm25(texts)
        if self.bm25 is None:
            self.bm25 = BM25()
            self.bm25.fit(texts)
            save_cached_bm25(self.bm25, texts)
        self._chunked_meta = get_chunked_meta()
        # Stage timing instrumentation (ms), reset on each retrieve()
        self.last_stage_times: dict[str, float] = {}
        self.cohere_api_key = cohere_api_key or os.environ.get("COHERE_API_KEY", "")
        if not self.cohere_api_key:
            try:
                from scraper.config.settings import get_settings
                self.cohere_api_key = get_settings().cohere_api_key
            except Exception:
                pass
        if self.cohere_api_key:
            self.reranker: Reranker = CohereRerank(
                api_key=self.cohere_api_key,
                model=cohere_rerank_model,
            )
            logger.info("HybridRetriever using Cohere Rerank")
        else:
            self.reranker = RerankFallback(self.embedder)
            logger.info("HybridRetriever using local RerankFallback")

        # Optional MMR wrapper to diversify the final results across techs.
        # Enable with RAG_MMR=1. Wraps the base reranker.
        if mmr_enabled():
            from rag.retrieval.reranker import MMRReranker
            lam = mmr_lambda()
            self.reranker = MMRReranker(self.reranker, lambda_=lam)
            logger.info("HybridRetriever wrapped reranker with MMR")

    async def retrieve(
        self,
        query: str,
        top_k_dense: int = 20,
        top_k_sparse: int = 20,
        top_k_rerank: int = 3,
    ) -> list[dict]:
        """Executa a recuperação híbrida: dense + sparse e, em seguida, rerank.

        Resultados bem-sucedidos são cacheados em memória (chave = query +
        top_k) — consultas repetidas no mesmo processo pulam as chamadas
        externas (Cohere/Qdrant) que causam picos de latência.
        """
        key = (query, top_k_dense, top_k_sparse, top_k_rerank)
        cached = _RETRIEVE_CACHE.get(key)
        if cached is not None:
            self.last_pre_rerank_keys = cached["pre_keys"]
            self.last_pre_rerank_scores = cached["pre_scores"]
            self.last_post_rerank_keys = cached["post_keys"]
            self.last_post_rerank_scores = cached["post_scores"]
            self.last_rerank_delta = cached["delta"]
            self.last_stage_times = {"cache": 0.0}
            return cached["results"]

        results = await self._retrieve_impl(query, top_k_dense, top_k_sparse, top_k_rerank)
        _RETRIEVE_CACHE[key] = {
            "results": results,
            "pre_keys": list(self.last_pre_rerank_keys),
            "pre_scores": list(self.last_pre_rerank_scores or []),
            "post_keys": list(self.last_post_rerank_keys),
            "post_scores": list(self.last_post_rerank_scores or []),
            "delta": dict(self.last_rerank_delta or {}),
        }
        return results

    async def _retrieve_impl(
        self,
        query: str,
        top_k_dense: int = 20,
        top_k_sparse: int = 20,
        top_k_rerank: int = 3,
    ) -> list[dict]:
        """Implementação da recuperação híbrida (sem cache)."""
        import time as _time
        self.last_stage_times = {}
        t0 = _time.perf_counter()

        # 0. Optional LLM query rewriting, then taxonomy query expansion.
        rewritten = await rewrite_query_with_llm(query)
        expanded = expand_query(rewritten)

        # 1. Dense retrieval from Qdrant — embeds with the same dim as the
        #    persisted collection (Cohere 1024 se a collection for 1024, senão
        #    Multilingual 384). Evita consultar 1024d numa collection 384d e
        #    degradivar para o scan in-process.
        if self._collection_dim is None:
            try:
                col = await self.qdrant.get_collection(self.collection)
                self._collection_dim = col.config.params.vectors.size
            except Exception:
                self._collection_dim = 0
        q_vec: list[float] | None = None
        try:
            if (
                getattr(self.embedder, "api_key", None)
                and self._collection_dim not in (0, 384)
            ):
                q_vec = (await self.embedder.embed_async([expanded]))[0].tolist()
            else:
                q_vec = self.embedder.embed_batch([expanded])[0].tolist()
        except Exception as e:
            logger.warning(f"Query embed failed ({e}); using multilingual embed")
            q_vec = self.embedder.embed_batch([expanded])[0].tolist()
        self.last_stage_times["expand_embed"] = (_time.perf_counter() - t0) * 1000
        t1 = _time.perf_counter()
        try:
            dense_results = await self.qdrant.query_points(
                collection_name=self.collection,
                query=q_vec,
                limit=top_k_dense,
            )
            dense_results = dense_results.points
            dense_docs = [
                {
                    "score": r.score,
                    "tech": r.payload.get("tech"),
                    "category": r.payload.get("category"),
                    "title": r.payload.get("title"),
                    "content": r.payload.get("content"),
                    "url": r.payload.get("url"),
                    "tags": r.payload.get("tags", []),
                    "source": "dense",
                }
                for r in dense_results
            ]
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            dense_docs = self._dense_local_fallback(expanded, top_k_dense) if local_dense_fallback() else []
        self.last_stage_times["dense"] = (_time.perf_counter() - t1) * 1000
        t2 = _time.perf_counter()

        # 2. Sparse BM25 retrieval over the chunked KB (using expanded query)
        corpus = get_chunked_texts()
        meta = self._chunked_meta
        sparse_scores = []
        for i, _doc in enumerate(corpus):
            s = self.bm25.score(expanded, i)
            sparse_scores.append((s, i))
        sparse_scores.sort(key=lambda x: -x[0])
        sparse_top = sparse_scores[:top_k_sparse]
        sparse_docs = []
        for score, idx in sparse_top:
            m = meta[idx]
            sparse_docs.append({
                "score": float(score),
                "tech": m.get("tech"),
                "category": m.get("category"),
                "title": m.get("title"),
                "content": m.get("content", ""),
                "url": m.get("url"),
                "tags": m.get("tags", []),
                "source": "bm25",
            })
        self.last_stage_times["sparse"] = (_time.perf_counter() - t2) * 1000
        t3 = _time.perf_counter()

        # 3. Metadata filtering / boosting: prefer chunks whose category or
        #    tags match the query domain.
        dense_docs = self._apply_category_boost(expanded, dense_docs)
        sparse_docs = self._apply_category_boost(expanded, sparse_docs)

        # 3.5 Deduplication: keep only the best chunk per parent (tech+title)
        dense_docs = self._dedup_by_parent(dense_docs)
        sparse_docs = self._dedup_by_parent(sparse_docs)

        # 4. Reciprocal Rank Fusion (configurável: k, cap, peso dense/sparse)
        fused = self._rrf(
            dense_docs, sparse_docs,
            k=rrf_k(), cap=rrf_cap(),
            dense_weight=rrf_dense_weight(), sparse_weight=rrf_sparse_weight(),
        )
        if not fused:
            return []
        self.last_stage_times["boost_dedup_rrf"] = (_time.perf_counter() - t3) * 1000
        t4 = _time.perf_counter()

        # 4.5 Telemetry: snapshot pre-rerank ordering of the fused candidate pool.
        pre_keys = [self._key_of(d) for d in fused]
        self.last_pre_rerank_keys = list(pre_keys)
        self.last_pre_rerank_scores = [float(d.get("score", 0.0) or 0.0) for d in fused]
        self.last_post_rerank_keys = []
        self.last_post_rerank_scores = []
        self.last_rerank_delta: dict = {}

        # 5. Rerank (try Cohere, fall back to local) using expanded query.
        #    RAG_RERANK=0 disables reranking (eval A/B: quality vs cost).
        if not rerank_enabled():
            final = list(fused[:top_k_rerank])
            for d in final:
                d["rerank_score"] = float(d.get("score", 0.0) or 0.0)
                d["rerank_source"] = "none"
        else:
            try:
                final = await self.reranker.rerank(expanded, fused, top_k=top_k_rerank)
            except Exception as e:
                logger.warning(f"Primary reranker failed ({e}); using local fallback")
                fallback = RerankFallback(self.embedder)
                final = await fallback.rerank(expanded, fused, top_k=top_k_rerank)
        self.last_stage_times["rerank"] = (_time.perf_counter() - t4) * 1000

        # 4.6 Telemetry: post-rerank ordering + effectiveness delta.
        self.last_post_rerank_keys = [self._key_of(d) for d in final]
        self.last_post_rerank_scores = [
            float(d.get("rerank_score", d.get("score", 0.0) or 0.0)) for d in final
        ]
        self.last_rerank_delta = self._rerank_delta(pre_keys, self.last_post_rerank_keys)

        # Reranker returns top_k_rerank; ensure diversity is respected
        final = self._dedup_by_parent(final)
        return final

    def _dense_local_fallback(self, query: str, top_k: int = 20) -> list[dict]:
        """Cosine-based dense retrieval against the shared chunk corpus.

        Used when Qdrant is unreachable or errors: instead of falling back to
        BM25-only, we embed the query and the corpus with the local multilingual
        embedder and rank by cosine similarity. Degrades quality vs Qdrant but
        keeps a real semantic signal even when the vector store is down.
        """
        corpus = get_chunked_texts()
        meta = self._chunked_meta
        corpus_key = _corpus_cache_key(corpus)
        vecs = _CORPUS_EMBEDDING_CACHE.get(corpus_key)
        if vecs is None:
            vecs = self.embedder.embed_batch(corpus)
            _CORPUS_EMBEDDING_CACHE[corpus_key] = vecs
            logger.info(f"Local dense fallback: embedded {len(vecs)} chunks for corpus {corpus_key}")

        q_vec = self.embedder.embed_batch([query])[0]
        q_norm = np.linalg.norm(q_vec)
        idx_scores = []
        for i, v in enumerate(vecs):
            n = np.linalg.norm(v)
            if q_norm == 0 or n == 0:
                idx_scores.append((i, 0.0))
                continue
            sim = float(np.dot(q_vec, v) / (q_norm * n))
            idx_scores.append((i, sim))
        idx_scores.sort(key=lambda x: -x[1])

        docs = []
        for idx, score in idx_scores[:top_k]:
            m = meta[idx]
            docs.append({
                "score": round(score, 6),
                "tech": m.get("tech"),
                "category": m.get("category"),
                "title": m.get("title"),
                "content": m.get("content", ""),
                "url": m.get("url"),
                "tags": m.get("tags", []),
                "source": "dense_local",
            })
        return docs

    @staticmethod
    def _key_of(doc: dict) -> str:
        return f"{_canonical_tech(doc.get('tech', ''))}:::{doc.get('title', '')}"

    def _rerank_delta(self, pre_keys: list[str], post_keys: list[str]) -> dict:
        """Measure how much the reranker changed the ordering of the pool.

        - reorder_fraction: share of returned items whose rank changed.
        - kendall_tau: rank correlation between pre/post order (0..1).
        - n_pool / n_returned: context for interpreting the delta.
        """
        if not post_keys:
            return {"reorder_fraction": 0.0, "kendall_tau": 0.0, "n_pool": len(pre_keys), "n_returned": 0}
        pre_pos = {k: i for i, k in enumerate(pre_keys)}
        changed = sum(1 for i, k in enumerate(post_keys) if pre_pos.get(k, i) != i)
        tau = self._kendall_tau(post_keys, pre_keys)
        return {
            "reorder_fraction": round(changed / len(post_keys), 4),
            "kendall_tau": round(tau, 4),
            "n_pool": len(pre_keys),
            "n_returned": len(post_keys),
        }

    @staticmethod
    def _kendall_tau(a: list[str], b: list[str]) -> float:
        """Tau-b over the ordering of `a` items within the `b` ordering."""
        b_pos = {k: i for i, k in enumerate(b)}
        order = [b_pos[k] for k in a if k in b_pos]
        n = len(order)
        if n < 2:
            return 0.0
        concordant = discordant = 0
        for i in range(n):
            for j in range(i + 1, n):
                if order[i] < order[j]:
                    concordant += 1
                elif order[i] > order[j]:
                    discordant += 1
        total = concordant + discordant
        return (concordant - discordant) / total if total else 0.0

    def _apply_category_boost(self, query: str, docs: list[dict]) -> list[dict]:
        """Reorder docs so those matching the query domain (category/tags) rank higher.

        Soft boost: category match adds a bounded bonus to the original score
        instead of a hard re-sort, so overall relevance stays the primary signal
        and a broad category match can't catapult an irrelevant chunk to #1.
        """
        q = query.lower()
        boost = category_boost()
        boosted = []
        for d in docs:
            cat = (d.get("category") or "").lower()
            tags = " ".join(d.get("tags") or []).lower()
            title = (d.get("title") or "").lower()
            # Detect domain keywords shared between the query and this chunk's
            # metadata. A match on a term that ALSO appears in the query is a
            # stronger relevance signal than a generic tag hit.
            shared = [
                k for k in
                ("inference", "serving", "speech", "robotics", "health",
                 "data science", "security", "generative", "image", "enterprise")
                if k in q and (k in cat or k in tags or k in title)
            ]
            bonus = boost * min(len(shared), 2)
            d["_cat_bonus"] = bonus
            d["_boosted_score"] = (d.get("score", 0.0) or 0.0) + bonus
            boosted.append(d)
        # Sort primarily by boosted score; keep stable original order for ties
        boosted.sort(key=lambda x: -x["_boosted_score"])
        return boosted

    def _dedup_by_parent(self, docs: list[dict]) -> list[dict]:
        """Keep only the highest-scoring doc per canonical (tech, title) group."""
        best: dict[tuple, dict] = {}
        for d in docs:
            key = (_canonical_tech(d.get("tech", "")), d.get("title", ""))
            cur = best.get(key)
            if cur is None or (d.get("score", 0) or 0) > (cur.get("score", 0) or 0):
                best[key] = d
        return list(best.values())

    def _rrf(
        self,
        dense: list[dict],
        sparse: list[dict],
        k: int = 55,
        cap: int = 20,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> list[dict]:
        """Reciprocal Rank Fusion with per-source weights.

        Keys on canonical (tech, title) — variações do mesmo nome de tech
        (RAPIDS/NVIDIA RAPIDS, Triton/NVIDIA Triton…) colapsam no mesmo bucket.
        dense_weight/sparse_weight let callers down-weight the noisier source
        (e.g. BM25 on tiny corpora).
        """
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        def key(doc: dict) -> str:
            return f"{_canonical_tech(doc.get('tech', ''))}:::{doc.get('title', '')}"

        for rank, doc in enumerate(dense):
            kk = key(doc)
            scores[kk] = scores.get(kk, 0) + dense_weight / (k + rank + 1)
            docs[kk] = doc
        for rank, doc in enumerate(sparse):
            kk = key(doc)
            scores[kk] = scores.get(kk, 0) + sparse_weight / (k + rank + 1)
            if kk not in docs:
                docs[kk] = doc

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [docs[kk] for kk, _ in ranked][:cap]


async def main() -> None:
    """Demo de recuperação híbrida com consultas representativas do domínio."""
    retriever = HybridRetriever()
    queries = [
        "How can I optimize LLM inference for production?",
        "What is the best solution for speech recognition in Portuguese?",
        "Tell me about NVIDIA Inception benefits for early-stage startups",
        "GPU-accelerated data processing for large datasets",
        "Computer vision for manufacturing quality control",
    ]
    for q in queries:
        print(f"\nQ: {q}")
        results = await retriever.retrieve(q, top_k_rerank=3)
        for r in results:
            print(f"  [{r.get('rerank_score', 0):.3f}] {r['tech']} — {r['title'][:60]}")


if __name__ == "__main__":
    asyncio.run(main())
