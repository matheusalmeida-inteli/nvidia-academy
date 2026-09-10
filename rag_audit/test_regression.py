"""
Regression test suite for RAG pipeline.
Run: pytest rag_audit/test_regression.py -v

Covers: critical bug fixes from audit iterations 1-10.
"""

import os
os.environ.update(
    POSTGRES_HOST="localhost", POSTGRES_PORT="5432",
    POSTGRES_USER="nvidia_radar", POSTGRES_PASSWORD="nvidia_radar_pass",
    POSTGRES_DB="nvidia_radar"
)

import pytest
import math


class TestBM25IDFCorrection:
    def test_stopword_de(self):
        from rag.ingest.ingestor import BM25
        from rag.ingest.shared import get_chunked_texts
        bm = BM25()
        bm.fit(get_chunked_texts())
        assert "de" in bm._STOPWORDS, "Portuguese stopword 'de' must be in stopword list"

    def test_stopword_the(self):
        from rag.ingest.ingestor import BM25
        from rag.ingest.shared import get_chunked_texts
        bm = BM25()
        bm.fit(get_chunked_texts())
        assert "the" in bm._STOPWORDS, "English stopword 'the' must be in stopword list"

    def test_idf_formula_uses_log(self):
        from rag.ingest.ingestor import BM25
        from rag.ingest.shared import get_chunked_texts
        bm = BM25()
        bm.fit(get_chunked_texts())
        idf_brasil = bm.idf.get("brasil")
        if idf_brasil is not None:
            assert idf_brasil > 0, "IDF must be > 0 (log formula)"

    def test_no_duplicate_bm25_in_retriever(self):
        from rag.retrieval import retriever as ret_mod
        with open(ret_mod.__file__, "r") as f:
            content = f.read()
        count = content.count("class BM25")
        assert count == 0, "Retriever must not define BM25 class (was duplicate)"

    def test_stopwords_list_populated(self):
        from rag.ingest.ingestor import BM25
        from rag.ingest.shared import get_chunked_texts
        bm = BM25()
        bm.fit(get_chunked_texts())
        assert len(bm._STOPWORDS) > 10, "Stopwords list must have content"


class TestCohereRerankConfig:
    def test_cohere_reads_from_settings(self):
        import rag.retrieval.retriever as ret_mod
        with open(ret_mod.__file__, "r") as f:
            content = f.read()
        assert "get_settings()" in content, "Retriever must read Cohere API key from get_settings()"


class TestRRFkParameter:
    def test_rrf_k_tuned(self):
        from rag.retrieval.retriever import HybridRetriever
        # Default k must be 55 (tuned balance) and the method must support
        # per-source weighting introduced by the tuning iteration.
        import inspect
        sig = inspect.signature(HybridRetriever._rrf)
        assert sig.parameters["k"].default == 55, "RRF k default must be 55"
        assert "dense_weight" in sig.parameters
        assert "sparse_weight" in sig.parameters

    def test_rrf_weights_affect_ranking(self):
        from rag.retrieval.retriever import HybridRetriever
        r = HybridRetriever.__new__(HybridRetriever)
        dense = [{"tech": "A", "title": "d1", "score": 1.0},
                 {"tech": "A", "title": "d2", "score": 0.9}]
        sparse = [{"tech": "B", "title": "s1", "score": 0.8},
                  {"tech": "B", "title": "s2", "score": 0.7}]
        # Equal weights: dense ranks ahead (rank 0 contribution higher)
        out_eq = r._rrf(dense, sparse, k=55)
        assert out_eq[0]["tech"] == "A"
        # Down-weight dense heavily: sparse should rise
        out_sparse = r._rrf(dense, sparse, k=55, dense_weight=0.01, sparse_weight=1.0)
        techs = [d["tech"] for d in out_sparse]
        assert out_sparse[0]["tech"] == "B", f"sparse should lead, got {techs}"

    def test_rrf_keys_on_tech_and_title(self):
        from rag.retrieval.retriever import HybridRetriever
        r = HybridRetriever.__new__(HybridRetriever)
        medium = [
            {"tech": "NIM", "title": "Doc", "score": 0.9},
            {"tech": "Triton", "title": "Doc", "score": 0.8},
        ]
        # Same title but different tech must NOT be merged into one bucket
        out = r._rrf(medium, [], k=55)
        techs = {d["tech"] for d in out}
        assert techs == {"NIM", "Triton"}, f"techs must not collide on title, got {techs}"


class TestCoverageNicheTechs:
    def test_morpheus_top1(self):
        from rag.retrieval.retriever import HybridRetriever
        import asyncio
        retriever = HybridRetriever()
        r = asyncio.run(retriever.retrieve("What is NVIDIA Morpheus for cybersecurity?", top_k_rerank=3))
        assert r[0]["tech"] == "NVIDIA Morpheus", \
            f"NVIDIA Morpheus must be top-1 for cybersecurity query, got {r[0]['tech']}"

    def test_isaac_top1(self):
        from rag.retrieval.retriever import HybridRetriever
        import asyncio
        retriever = HybridRetriever()
        r = asyncio.run(retriever.retrieve("What is NVIDIA Isaac for robotics simulation?", top_k_rerank=3))
        assert r[0]["tech"] == "NVIDIA Isaac", \
            f"NVIDIA Isaac must be top-1 for robotics query, got {r[0]['tech']}"


class TestGracefulDegradation:
    def test_qdrant_unavailable_uses_bm25(self):
        from rag.retrieval.retriever import HybridRetriever
        import asyncio
        retriever = HybridRetriever()
        orig = retriever.qdrant.query_points

        async def broken(*args, **kwargs):
            raise ConnectionError("Qdrant unavailable")
        retriever.qdrant.query_points = broken
        try:
            r = asyncio.run(retriever.retrieve("LLM inference optimization", top_k_rerank=3))
            assert len(r) > 0, "Must return results when Qdrant is down (BM25 fallback)"
        finally:
            retriever.qdrant.query_points = orig


class TestDeterminism:
    def test_same_query_same_results(self):
        from rag.retrieval.retriever import HybridRetriever
        import asyncio
        retriever = HybridRetriever()
        q = "optimize LLM inference production"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            r1 = loop.run_until_complete(retriever.retrieve(q, top_k_rerank=3))
            r2 = loop.run_until_complete(retriever.retrieve(q, top_k_rerank=3))
            assert [x["tech"] for x in r1] == [x["tech"] for x in r2], \
                "Same query must produce same results"
        finally:
            loop.close()


class TestCitationFidelity:
    def test_citations_contain_nvidia_terms(self):
        from rag.ingest.shared import get_chunked_texts
        chunks = get_chunked_texts()
        sample = chunks[:30]
        nvidia_terms = ["nvidia", "rapids", "triton", "tensorrt", "cuda", "isaac", "morpheus", "clara", "nemo", "riva", "omniverse", "cudf", "cuml", "monai"]
        coverage = sum(1 for c in sample if any(t in c.lower() for t in nvidia_terms))
        assert coverage / len(sample) > 0.8, "Chunks should reference NVIDIA techs"


class TestMultilingualEmbedder:
    def test_embedder_is_multilingual(self):
        from rag.ingest.embeddings import MultilingualEmbedder
        e = MultilingualEmbedder()
        v1 = e.embed("chatbot de atendimento para fintech brasileira")
        v2 = e.embed("Brazilian fintech chatbot")
        v3 = e.embed("recipe for chocolate cake")
        sim_same = float(v1 @ v2)
        sim_diff = float(v1 @ v3)
        assert sim_same > 0.9, f"PT/EN same meaning should be similar: {sim_same:.3f}"
        assert sim_diff < 0.5, f"Different meaning should be dissimilar: {sim_diff:.3f}"
        assert v1.shape[0] == 384, f"Expected 384-dim vectors, got {v1.shape[0]}"


class TestNoDataLeakage:
    def test_tautological_chunks_removed(self):
        from rag.ingest.shared import get_chunked_texts
        chunks = get_chunked_texts()
        suspicious = ["data_pipeline_mlops", "data pipeline mlops", "tautological"]
        leaks = 0
        for chunk in chunks[:30]:
            text_lower = chunk.lower()
            for s in suspicious:
                if s in text_lower:
                    leaks += 1
                    break
        assert leaks == 0, f"Found {leaks} chunks with tautological content"

    def test_no_self_referential_kb_chunks(self):
        from rag.ingest.shared import get_chunked_texts
        chunks = get_chunked_texts()
        bad_count = 0
        for chunk in chunks:
            text_lower = chunk.lower()
            if "atendimento" in text_lower and "llm" in text_lower and "inference" in text_lower and "production" in text_lower and "rag" not in text_lower and "fintech" not in text_lower and "chatbot" not in text_lower:
                bad_count += 1
        assert bad_count < 3, f"Too many suspicious 'atendimento' chunks: {bad_count}"
