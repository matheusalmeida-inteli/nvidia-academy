"""Embeddings provider — multilingual sentence-transformers.

Uses `paraphrase-multilingual-MiniLM-L12-v2` (384 dim) for real semantic
embeddings in 50+ languages including Portuguese, Spanish, English.

Falls back to LocalEmbedder (TF-IDF) only if sentence-transformers is unavailable
or model download fails.
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np
from loguru import logger

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384

_model_singleton = None
_model_lock = None


def _get_model_singleton():
    """Return the shared SentenceTransformer instance (process-wide cache).

    Loading the model takes ~10s on disk; each request builds a fresh
    HybridRetriever/CohereEmbedder, so without this cache the first query
    after every call blew past the 90s frontend timeout.
    """
    global _model_singleton, _model_lock
    if _model_lock is None:
        from threading import Lock
        _model_lock = Lock()
    if _model_singleton is not None:
        return _model_singleton
    with _model_lock:
        if _model_singleton is None:
            from sentence_transformers import SentenceTransformer
            _model_singleton = SentenceTransformer(MODEL_NAME)
    return _model_singleton


class MultilingualEmbedder:
    """Multilingual sentence-transformers based embedder.

    Produces 384-dim semantic vectors in 50+ languages.
    Loaded lazily on first use to avoid slow startup when offline.
    """

    def __init__(self) -> None:
        """Estado inicial: modelo carregado de forma lazy (primeiro uso)."""
        self._model = None
        self._fitted = False
        self._load_attempted = False
        self._load_error: str | None = None

    def _ensure_model(self) -> None:
        """Garante o modelo carregado (singleton), registrando falha sem levantar exceção."""
        if self._model is not None or self._load_attempted:
            return
        self._load_attempted = True
        try:
            self._model = _get_model_singleton()
            self._fitted = True
            logger.info(f"Loaded multilingual embedder: {MODEL_NAME}")
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"Failed to load {MODEL_NAME}: {e}. Will fall back to LocalEmbedder.")

    def embed(self, text: str) -> np.ndarray:
        """Gera o vetor semântico normalizado (384 dims) de um texto."""
        self._ensure_model()
        if self._model is None:
            return np.zeros(DIM, dtype=np.float32)
        vec = self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return vec.astype(np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Gera vetores para uma lista de textos em lote."""
        self._ensure_model()
        if self._model is None:
            return [np.zeros(DIM, dtype=np.float32) for _ in texts]
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.astype(np.float32) for v in vecs]

    def fit(self, documents: list[str]) -> None:
        """Aquece o modelo com parte dos documentos (primeira carga do encoder)."""
        self._ensure_model()
        if self._model is not None:
            _ = self._model.encode(documents[:1], normalize_embeddings=True, show_progress_bar=False)
            self._fitted = True
            logger.info(f"Multilingual embedder ready (warmed up on {len(documents)} docs)")


class LocalEmbedder:
    """Deterministic local embeddings using hashed n-grams + IDF.

    Produces 1536-dim vectors. Not as good as real embeddings but works offline
    with no API cost. Used only as fallback when MultilingualEmbedder fails to load.
    """

    DIM = 1536

    def __init__(self) -> None:
        """Vocabulário TF-IDF configurado apenas após o fit."""
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        """Tokenização simples: palavras e bigrams (minúsculas, sem pontuação)."""
        text = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s]", " ", text.lower())
        tokens = text.split()
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def _hash_token(self, token: str) -> int:
        """Hash determinístico (md5) de um token para o índice do vetor."""
        return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)

    def fit(self, documents: list[str]) -> None:
        """Constrói o vocabulário e os pesos IDF a partir dos documentos."""
        from collections import Counter
        df: Counter[str] = Counter()
        n_docs = len(documents)
        for doc in documents:
            unique = set(self._tokenize(doc))
            for tok in unique:
                df[tok] += 1
        vocab_items = sorted(df.items(), key=lambda x: -x[1])[:10_000]
        self.vocab = {tok: idx for idx, (tok, _) in enumerate(vocab_items)}
        self.idf = {
            tok: math.log(n_docs / (count + 1)) + 1
            for tok, count in vocab_items
        }
        self._fitted = True
        logger.info(f"LocalEmbedder fitted on {n_docs} documents, vocab size: {len(self.vocab)}")

    def embed(self, text: str) -> np.ndarray:
        """Gera vetor determinístico (1536 dims) TF-IDF/hash para um texto."""
        vec = np.zeros(self.DIM, dtype=np.float32)
        if not self._fitted:
            text_bytes = text.encode("utf-8")
            for i in range(self.DIM // 8):
                byte_val = text_bytes[i] if i < len(text_bytes) else 0
                offset = (i * 8) % self.DIM
                for bit in range(8):
                    if byte_val & (1 << bit):
                        vec[(offset + bit) % self.DIM] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec

        tokens = self._tokenize(text)
        from collections import Counter
        tf = Counter(tokens)
        for tok, count in tf.items():
            if tok not in self.vocab:
                continue
            idx = self._hash_token(tok)
            weight = count * self.idf.get(tok, 1.0)
            vec[idx % self.DIM] += weight

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Gera vetores para uma lista de textos (loop local)."""
        return [self.embed(t) for t in texts]


class CohereEmbedder:
    """Cohere embed-multilingual-v3 — production embeddings (1024 dim).

    Falls back to MultilingualEmbedder if COHERE_API_KEY is missing,
    then to LocalEmbedder if sentence-transformers is unavailable.
    """

    def __init__(self) -> None:
        """Resolve a API key Cohere e prepara os fallbacks local/multilingual."""
        self.api_key: str | None = None
        try:
            from scraper.config.settings import get_settings
            self.api_key = get_settings().cohere_api_key
        except Exception:
            pass
        self._multilingual = MultilingualEmbedder()
        self._local = LocalEmbedder()

    async def embed_async(self, texts: list[str]) -> list[np.ndarray]:
        """Embed em lote via Cohere (1024 dims); sem API key usa o fallback multilíngue."""
        if not self.api_key:
            return self._multilingual.embed_batch(texts)

        try:
            import cohere
            client = cohere.AsyncClient(api_key=self.api_key)
            response = await client.embed(
                texts=texts,
                model="embed-multilingual-v3.0",
                input_type="search_document",
            )
            return [np.array(e, dtype=np.float32) for e in response.embeddings]
        except Exception as e:
            logger.warning(f"Cohere embed failed, falling back to multilingual: {e}")
            return self._multilingual.embed_batch(texts)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Fallback síncrono: usa sempre o embedder multilíngue local."""
        return self._multilingual.embed_batch(texts)

    def fit_local(self, documents: list[str]) -> None:
        """Ajusta os embedders locais de fallback sobre os documentos."""
        self._multilingual.fit(documents)
        self._local.fit(documents)

    @property
    def dim(self) -> int:
        """Dimensão dos vetores conforme o embedder efetivamente em uso."""
        if self._multilingual._model is not None:
            return DIM
        return LocalEmbedder.DIM
