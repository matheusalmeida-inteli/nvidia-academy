"""Pre-computed semantic chunks of the NVIDIA KB.

Cached at module level so both the ingestor and the retriever use the same
chunk texts for BM25 fitting and Qdrant ingestion.

Usage:
    from rag.ingest.shared import CHUNKED_PAIRS, CHUNKED_TEXTS, CHUNKED_META
"""
from __future__ import annotations

from loguru import logger

from rag.config import chunk_max, chunk_overlap, chunk_target, semantic_chunking

# Module-level cache
_CACHE: dict | None = None


def _build_cache():
    """Compute and cache semantic chunks. Called once per process lifetime."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    try:
        from rag.ingest.chunker import SemanticChunker, chunk_kb
        from rag.ingest.nvidia_kb import NVIDIA_KB

        use_semantic = semantic_chunking()
        target_size = chunk_target()
        max_size = chunk_max()
        overlap = chunk_overlap()
        if use_semantic:
            chunker = SemanticChunker(
                target_size=target_size,
                max_size=max_size,
                overlap=overlap,
                use_semantic_break=True,
            )
            pairs = chunk_kb(chunker, NVIDIA_KB)
            texts = [child.text for _, child in pairs]
            meta = [
                {
                    "parent_id": parent.id,
                    "tech": child.metadata.get("tech", ""),
                    "category": child.metadata.get("category", ""),
                    "title": child.metadata.get("title", ""),
                    "url": child.metadata.get("url", ""),
                    "tags": child.metadata.get("tags", []),
                    "position": child.metadata.get("position", 0),
                    "content": child.text,
                }
                for parent, child in pairs
            ]
            logger.info(
                f"Shared cache built: {len(texts)} semantic chunks "
                f"from {len(NVIDIA_KB)} parent docs"
            )
        else:
            texts = [c.content for c in NVIDIA_KB]
            meta = [
                {
                    "parent_id": c.id,
                    "tech": c.tech,
                    "category": c.category,
                    "title": c.title,
                    "url": c.url,
                    "tags": c.tags,
                    "position": 0,
                    "content": c.content,
                }
                for c in NVIDIA_KB
            ]
            logger.info(f"Shared cache built: {len(texts)} parent chunks (semantic disabled)")

        _CACHE = {"texts": texts, "meta": meta}
        return _CACHE
    except Exception as e:
        logger.warning(f"Failed to build shared chunk cache: {e}")
        _CACHE = {"texts": [], "meta": []}
        return _CACHE


def get_chunked_texts() -> list[str]:
    """Retorna os textos dos chunks semânticos (cache compartilhado)."""
    return _build_cache()["texts"]


def get_chunked_meta() -> list[dict]:
    """Retorna os metadados dos chunks (parent_id, tech, url, etc.)."""
    return _build_cache()["meta"]
