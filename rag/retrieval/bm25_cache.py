"""Disk cache for the fitted BM25 index.

The BM25 index depends only on the chunked corpus. Because the corpus is
stable between runs (same KB + same chunks), we can fit once and reload from
disk on subsequent starts instead of refitting on every HybridRetriever init.

The cache is keyed by a hash of the corpus, so if the KB/chunks change the
index is automatically invalidated and refitted.
"""
from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path

from loguru import logger

CACHE_DIR = Path(os.environ.get("RAG_CACHE_DIR", "/tmp/rag_cache"))
CACHE_FILE = CACHE_DIR / "bm25.pkl"


def _corpus_hash(texts: list[str]) -> str:
    """Gera o hash SHA-256 do corpus (chave de invalidação do cache)."""
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8"))
    return h.hexdigest()


def load_cached_bm25(texts: list[str]):
    """Return a fitted BM25 if a valid cache exists, else None.

    BM25 is imported lazily to avoid a circular import at module load.
    """
    try:
        if not CACHE_FILE.exists():
            return None
        with open(CACHE_FILE, "rb") as f:
            payload = pickle.load(f)
        if payload.get("corpus_hash") != _corpus_hash(texts):
            logger.info("BM25 cache invalidated (corpus changed); refitting.")
            return None
        bm25 = payload["bm25"]
        logger.info(f"Loaded BM25 from cache ({CACHE_FILE.name})")
        return bm25
    except Exception as e:
        logger.warning(f"Failed to load BM25 cache: {e}")
        return None


def save_cached_bm25(bm25, texts: list[str]) -> None:
    """Persist a fitted BM25 together with its corpus hash."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(
                {"corpus_hash": _corpus_hash(texts), "bm25": bm25},
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.info(f"Saved BM25 to cache ({CACHE_FILE.name})")
    except Exception as e:
        logger.warning(f"Failed to save BM25 cache: {e}")
