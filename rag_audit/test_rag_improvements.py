"""Tests for the 12 RAG improvement features (iteration 9).

Run: pytest rag_audit/test_rag_improvements.py -v

Covers: bm25_cache, MMR reranker, citation validation, chunking defaults,
query expansion, dedup, latency instrumentation, eval_e2e helpers, golden set.
Note: slow/network-bound retriever tests are kept minimal (BM25/mocking).
"""

import os
os.environ.update(
    POSTGRES_HOST="localhost", POSTGRES_PORT="5432",
    POSTGRES_USER="nvidia_radar", POSTGRES_PASSWORD="nvidia_radar_pass",
    POSTGRES_DB="nvidia_radar"
)

import pytest


class TestChunkingDefaults:
    def test_defaults_updated(self):
        from rag.ingest.chunker import SemanticChunker
        c = SemanticChunker.__init__ if hasattr(SemanticChunker, "__init__") else None
        import inspect
        sig = inspect.signature(SemanticChunker.__init__)
        params = sig.parameters
        assert params.get("target_size").default == 800
        assert params.get("max_size").default == 1600
        assert params.get("overlap").default == 200

    def test_shared_defaults_env_driven(self):
        from rag.ingest import shared
        import rag.config as cfg
        # After config centralization shared delegates to rag.config.
        assert callable(cfg.chunk_target) and cfg.chunk_target() == 800
        assert callable(cfg.chunk_max) and cfg.chunk_max() == 1600
        assert callable(cfg.chunk_overlap) and cfg.chunk_overlap() == 200


class TestQueryExpansion:
    def test_expansion_appends_domain_terms(self):
        from rag.retrieval.retriever import expand_query
        expanded = expand_query("fintech fraud detection")
        assert "morpheus" in expanded.lower()
        assert "rapids" in expanded.lower()
        assert expanded.startswith("fintech fraud detection")

    def test_no_match_keeps_original(self):
        from rag.retrieval.retriever import expand_query
        q = "random unrelated query xyz 123"
        assert expand_query(q) == q


class TestDedupByParent:
    def test_dedup_keeps_highest_score(self):
        from rag.retrieval.retriever import HybridRetriever
        r = HybridRetriever.__new__(HybridRetriever)
        docs = [
            {"tech": "NVIDIA NIM", "title": "same", "score": 0.9},
            {"tech": "NVIDIA NIM", "title": "same", "score": 0.5},
            {"tech": "RAPIDS", "title": "other", "score": 0.7},
        ]
        out = r._dedup_by_parent(docs)
        nim = [d for d in out if d["tech"] == "NVIDIA NIM"]
        assert len(nim) == 1
        assert nim[0]["score"] == 0.9
        assert len(out) == 2


class TestMMRReranker:
    async def _fake_base_rerank(self, query, docs, top_k):
        # relevance = score, higher first
        return sorted(docs, key=lambda d: -d["score"])[:top_k]

    def test_mmr_respects_topk(self):
        import asyncio
        from rag.retrieval.reranker import MMRReranker
        base = type("Base", (), {"rerank": self._fake_base_rerank})()
        mmr = MMRReranker(base, lambda_=0.7)
        docs = [
            {"tech": f"T{i}", "content": f"text {i} " * 20, "score": 1.0 - i * 0.1}
            for i in range(10)
        ]
        out = asyncio.run(mmr.rerank("q", docs, top_k=3))
        assert len(out) == 3
        # MMR with diversity should not all be the top-3 by relevance alone
        assert len({d["tech"] for d in out}) == 3


class TestBm25Cache:
    def test_roundtrip_preserves_fitted(self, tmp_path, monkeypatch):
        from rag.retrieval import bm25_cache
        import rag.ingest.ingestor as ing
        monkeypatch.setattr(bm25_cache, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(bm25_cache, "CACHE_FILE", tmp_path / "bm25.pkl")
        texts = ["NVIDIA NIM serve models", "RAPIDS accelerate data", "Triton inference"]

        bm = ing.BM25()
        bm.fit(texts)
        bm25_cache.save_cached_bm25(bm, texts)

        loaded = bm25_cache.load_cached_bm25(texts)
        assert loaded is not None
        # Same score for same query/doc index
        assert loaded.score("NVIDIA", 0) == bm.score("NVIDIA", 0)

    def test_invalidated_on_corpus_change(self, tmp_path, monkeypatch):
        from rag.retrieval import bm25_cache
        import rag.ingest.ingestor as ing
        monkeypatch.setattr(bm25_cache, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(bm25_cache, "CACHE_FILE", tmp_path / "bm25.pkl")
        bm = ing.BM25()
        bm.fit(["tech a", "tech b"])
        bm25_cache.save_cached_bm25(bm, ["tech a", "tech b"])
        loaded = bm25_cache.load_cached_bm25(["DIFFERENT", "corpus"])
        assert loaded is None


class TestCitationValidation:
    def test_grounded_citation_valid(self):
        from agents.nodes.nvidia_rag import validate_citations
        refs = [
            {"tech": "NVIDIA NIM", "title": "NIM deployment",
             "content": "NVIDIA NIM lets you serve LLM models with low latency", "score": 1.0},
            {"tech": "Triton", "title": "x",
             "content": "no mention of the tech in the chunk body", "score": 0.9},
        ]
        out = validate_citations(refs)
        assert out[0]["valid"] is True
        assert out[1]["valid"] is False

    def test_alias_variant_grounds(self):
        from agents.nodes.nvidia_rag import validate_citations
        refs = [{"tech": "TensorRT-LLM", "title": "t",
                 "content": "tensorrt-llm speeds up inference", "score": 1.0}]
        assert validate_citations(refs)[0]["valid"] is True


class TestLatencyInstrumentation:
    def test_stage_times_populated(self):
        import asyncio
        from rag.retrieval.retriever import HybridRetriever
        retriever = HybridRetriever()
        orig = retriever.reranker.rerank

        async def fake_rerank(q, docs, top_k=3):
            return docs[:top_k]

        retriever.reranker.rerank = fake_rerank
        try:
            asyncio.run(retriever.retrieve("LLM inference", top_k_rerank=2))
            assert set(retriever.last_stage_times) >= {
                "expand_embed", "dense", "sparse", "rerank"}
            for v in retriever.last_stage_times.values():
                assert v >= 0
        finally:
            retriever.reranker.rerank = orig


class TestEvalHelpers:
    def test_normalize(self):
        from rag.eval.eval_e2e import _normalize
        assert _normalize("NVIDIA NIM") == "nim"
        assert _normalize("TensorRT-LLM") == "tensorrt llm"

    def test_matches(self):
        from rag.eval.eval_e2e import _matches
        assert _matches("NVIDIA NIM", "NVIDIA NIM")
        assert _matches("NVIDIA Clara", "Clara")
        assert _matches("NVIDIA Triton Inference Server", "Triton")
        assert not _matches("RAPIDS", "cuML")


class TestGoldenSetExpanded:
    def test_golden_set_has_pt_and_ambiguous(self):
        from rag.eval.golden_set import EVAL_SAMPLES
        ids = [s["id"] for s in EVAL_SAMPLES]
        assert len(EVAL_SAMPLES) >= 30
        assert any(i.startswith("p") for i in ids), "Portuguese samples missing"
        assert any(i.startswith("a") for i in ids), "Ambiguous samples missing"


class TestRAGtuning:
    def test_category_boost_is_soft_additive(self):
        from rag.retrieval.retriever import HybridRetriever
        r = HybridRetriever.__new__(HybridRetriever)
        q = "LLM inference production"
        docs = [
            # much higher score but category-neutral
            {"tech": "Triton", "title": "Serving", "category": "mlops",
             "tags": [], "score": 0.95},
            # low score but category matches query domain
            {"tech": "NIM", "title": "NIM", "category": "inference",
             "tags": [], "score": 0.40},
        ]
        out = r._apply_category_boost(q, docs)
        # Soft boost must NOT override a clear relevance gap (0.95 vs 0.40)
        assert out[0]["tech"] == "Triton", \
            "Category boost must not override clear relevance difference"
        # Category-matching chunk should get a bonus recorded
        nim = next(d for d in out if d["tech"] == "NIM")
        assert nim["_cat_bonus"] > 0

    def test_category_boost_recorded_without_mutation_leak(self):
        from rag.retrieval.retriever import HybridRetriever
        r = HybridRetriever.__new__(HybridRetriever)
        docs = [{"tech": "X", "title": "t", "category": "inference", "tags": [], "score": 0.5}]
        out = r._apply_category_boost("inference serving", docs)
        assert "_cat_bonus" in out[0]
        assert out[0]["_boosted_score"] >= 0.5
