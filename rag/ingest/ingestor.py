"""RAG ingestion — load NVIDIA KB into Qdrant with hybrid retrieval.

BM25 scores are stored as a payload field for lexical search.
"""
from __future__ import annotations

import asyncio
import hashlib

import numpy as np
from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from rag.config import chunk_max, chunk_overlap, chunk_target
from rag.ingest.chunker import SemanticChunker
from rag.ingest.embeddings import DIM, CohereEmbedder
from rag.ingest.shared import get_chunked_meta, get_chunked_texts

COLLECTION = "nvidia_knowledge"


class BM25:
    """Lightweight BM25 for lexical search."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """Configura os parâmetros do BM25 (k1, b)."""
        self.k1 = k1
        self.b = b
        self.avgdl = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.doc_len: list[int] = []
        self.corpus: list[list[str]] = []

    _STOPWORDS = {
        "a", "à", "ao", "aos", "as", "á", "ã", "â",
        "da", "das", "de", "dela", "delas", "dele", "delos", "deste",
        "do", "dos", "e", "é", "em", "entre", "essa", "essas", "esse",
        "esses", "esta", "estas", "este", "estes", "eu", "foi", "for",
        "há", "isso", "ista", "isto", "já", "lhe", "lo", "mas", "me",
        "meu", "meus", "no", "nos", "o", "os", "ou", "para", "pela",
        "pelas", "pelo", "pelos", "por", "qual", "que", "se", "seja",
        "sem", "ser", "sera", "serão", "seu", "seus", "só", "são", "sua",
        "suas", "também", "teu", "teus", "tu", "tua", "tuas", "um",
        "uma", "umas", "uns", "vos", "vossa", "vossas", "vosso", "vossos",
        "the", "and", "of", "in", "to", "is", "on", "with", "at", "by", "or", "an", "it", "its", "from", "be", "are",
        "was", "were", "been", "has", "have", "had", "this", "that",
        "these", "those", "not", "but", "can", "will", "all", "any",
    }

    def fit(self, corpus: list[str]) -> None:
        """Tokeniza o corpus e calcula doc lengths, avgdl, DF e IDF (fórmula log)."""
        import re
        from collections import Counter

        def tokenize(text: str) -> list[str]:
            tokens = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s]", " ", text.lower()).split()
            return [t for t in tokens if len(t) >= 2 and t not in self._STOPWORDS]

        self.corpus = [tokenize(doc) for doc in corpus]
        self.doc_len = [len(doc) for doc in self.corpus]
        self.avgdl = sum(self.doc_len) / max(len(self.corpus), 1)

        df: Counter[str] = Counter()
        for doc in self.corpus:
            for tok in set(doc):
                df[tok] += 1
        self.doc_freqs = dict(df)
        import math
        n = len(self.corpus)
        self.idf = {
            tok: max(0.0, math.log((n - freq + 0.5) / (freq + 0.5)) + 1)
            for tok, freq in self.doc_freqs.items()
        }
        logger.info(f"BM25 fitted on {n} documents, vocab={len(self.idf)}")

    def score(self, query: str, doc_idx: int) -> float:
        """Computa o score BM25 de um documento (doc_idx) para a consulta."""
        import re
        q_tokens = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s]", " ", query.lower()).split()
        q_tokens = [t for t in q_tokens if len(t) >= 2 and t not in self._STOPWORDS]
        doc = self.corpus[doc_idx]
        doc_tf: dict[str, int] = {}
        for tok in doc:
            doc_tf[tok] = doc_tf.get(tok, 0) + 1

        score = 0.0
        for tok in q_tokens:
            if tok not in doc_tf:
                continue
            tf = doc_tf[tok]
            idf = self.idf.get(tok, 0)
            score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * self.doc_len[doc_idx] / self.avgdl))
        return score


class NVIDIAIngestor:
    """Ingest NVIDIA KB into Qdrant."""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection: str = COLLECTION,
        use_semantic_chunking: bool = True,
        chunk_target_size: int | None = None,
        chunk_max_size: int | None = None,
    ) -> None:
        """Prepara cliente Qdrant, embedder, BM25 e chunker (se ativo).

        Parâmetros de chunking vêm da config central (RAG_CHUNK_TARGET/MAX),
        não de defaults locais divergentes.
        """
        self.qdrant = AsyncQdrantClient(url=qdrant_url)
        self.collection = collection
        self.embedder = CohereEmbedder()
        self.bm25 = BM25()
        self.use_semantic_chunking = use_semantic_chunking
        self.chunker = (
            SemanticChunker(
                target_size=chunk_target_size or chunk_target(),
                max_size=chunk_max_size or chunk_max(),
                overlap=chunk_overlap(),
                use_semantic_break=True,
            )
            if use_semantic_chunking
            else None
        )

    async def create_collection(self) -> None:
        """(Re)cria a collection Qdrant com dimensão e distância cosseno detectadas."""
        try:
            await self.qdrant.delete_collection(self.collection)
            logger.info(f"Deleted existing collection: {self.collection}")
        except Exception:
            pass

        # Probe a single text to determine actual vector dimension.
        # Uses the same embedding source as ingest(): Cohere (1024) when
        # API key present, else Multilingual (384).
        if hasattr(self.embedder, "api_key") and self.embedder.api_key:
            try:
                # Mesmo caminho da ingestão/consulta: async usa Cohere (1024).
                # embed_batch() síncrono é sempre o multilíngue (384) e criaria
                # uma collection de dimensão divergente da ingestão.
                probe_vectors = await self.embedder.embed_async(["probe"])
                if probe_vectors and len(probe_vectors[0]):
                    actual_dim = len(probe_vectors[0])
                else:
                    actual_dim = self.embedder.dim
            except Exception:
                actual_dim = self.embedder.dim
        elif hasattr(self.embedder, "_multilingual"):
            probe = self.embedder._multilingual.embed(["probe"])[0]
            actual_dim = len(probe)
        else:
            probe = self.embedder.embed_batch(["probe"])[0]
            actual_dim = len(probe) if hasattr(probe, "__len__") else DIM

        await self.qdrant.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=actual_dim,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info(f"Collection '{self.collection}' created (dim={actual_dim})")

    async def ingest(self) -> int:
        """Gera embeddings dos chunks, fitta o BM25 e faz upsert no Qdrant.

        Retorna a quantidade de pontos persistidos. As dimensões/IDs dos
        pontos são determinísticos (hash de parent + hash do texto).
        """
        # Use shared chunk cache so Qdrant + BM25 stay in sync
        texts = get_chunked_texts()
        meta = get_chunked_meta()
        logger.info(f"Ingesting {len(texts)} chunks")

        self.bm25.fit(texts)

        if hasattr(self.embedder, "_local"):
            self.embedder.fit_local(texts)

        # Use Cohere embed (1024 dim) when COHERE_API_KEY is set, else
        # MultilingualEmbedder (384 dim) for ingestion. Both are compatible
        # with the collection created by create_collection (dynamic dim probe).
        if hasattr(self.embedder, "api_key") and self.embedder.api_key:
            try:
                import asyncio
                vectors = asyncio.run(self.embedder.embed_async(texts))
                logger.info(f"Embedded {len(vectors)} chunks with Cohere embed-multilingual-v3.0 ({len(vectors[0])} dim)")
            except Exception as e:
                logger.warning(f"Cohere embed_async failed ({e}); falling back to MultilingualEmbedder")
                vectors = self.embedder._multilingual.embed_batch(texts)
                logger.info(f"Embedded {len(vectors)} chunks with MultilingualEmbedder (paraphrase-multilingual-MiniLM-L12-v2)")
        elif hasattr(self.embedder, "_multilingual"):
            vectors = self.embedder._multilingual.embed_batch(texts)
            logger.info(f"Embedded {len(vectors)} chunks with MultilingualEmbedder (paraphrase-multilingual-MiniLM-L12-v2)")
        else:
            vectors = self.embedder.embed_batch(texts)
            logger.info(f"Embedded {len(vectors)} chunks with fallback")

        points = []
        for i in range(len(texts)):
            vector = vectors[i].tolist() if isinstance(vectors[i], np.ndarray) else vectors[i]
            chunk_meta = meta[i]
            parent_id = chunk_meta["parent_id"]

            # Qdrant accepts integer or UUID only
            base_hash = hashlib.md5(parent_id.encode()).hexdigest()
            child_hash = hashlib.md5(texts[i].encode()).hexdigest()[:8]
            point_uuid = (
                f"{base_hash[:8]}-{base_hash[8:12]}-{base_hash[12:16]}-"
                f"{base_hash[16:20]}-{child_hash}{base_hash[24:28]}"
            )

            points.append(
                models.PointStruct(
                    id=point_uuid,
                    vector=vector,
                    payload={
                        "parent_id": parent_id,
                        "tech": chunk_meta.get("tech", ""),
                        "category": chunk_meta.get("category", ""),
                        "title": chunk_meta.get("title", ""),
                        "content": texts[i],
                        "url": chunk_meta.get("url", ""),
                        "tags": chunk_meta.get("tags", []),
                        "position": chunk_meta.get("position", 0),
                    },
                )
            )

        await self.qdrant.upsert(
            collection_name=self.collection,
            points=points,
        )
        logger.info(f"Ingested {len(points)} chunks into '{self.collection}'")
        return len(points)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """Busca densa simples na collection (somente embeddings)."""
        q_vec = self.embedder.embed_batch([query])[0].tolist()
        results = await self.qdrant.query_points(
            collection_name=self.collection,
            query=q_vec,
            limit=top_k,
            score_threshold=score_threshold,
        )
        results = results.points
        return [
            {
                "score": r.score,
                "tech": r.payload.get("tech"),
                "category": r.payload.get("category"),
                "title": r.payload.get("title"),
                "content": r.payload.get("content"),
                "url": r.payload.get("url"),
                "tags": r.payload.get("tags", []),
            }
            for r in results
        ]


async def main() -> None:
    """Roda a ingestão completa (cria collection, ingere e testa busca)."""
    ingestor = NVIDIAIngestor()
    await ingestor.create_collection()
    await ingestor.ingest()

    results = await ingestor.search("LLM inference optimization", top_k=3)
    print(f"\nSearch test: found {len(results)} results")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['tech']} — {r['title']}")


if __name__ == "__main__":
    asyncio.run(main())
