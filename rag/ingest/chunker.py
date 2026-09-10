"""Semantic chunker — splits documents by sentence-boundary + semantic distance.

Strategy:
1. Split text into sentences using regex.
2. Group sentences into candidate chunks of ~target_size characters.
3. Optionally refine by computing embedding distance between consecutive
   groups and splitting where the distance exceeds a threshold
   (semantic breakpoint).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from rag.config import chunk_max, chunk_overlap, chunk_target
from rag.ingest.embeddings import LocalEmbedder

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁ-Ý])|(?<=\.)\s*\n")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation + capitalization heuristics."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p and len(p.strip()) > 5]


@dataclass
class TextChunk:
    """Chunk de texto com posição (ordem), parent_id e metadados do documento pai."""
    text: str
    position: int
    parent_id: str
    metadata: dict = field(default_factory=dict)


class SemanticChunker:
    """Sentence-grouping chunker with optional semantic distance breakpoints."""

    def __init__(
        self,
        target_size: int = 800,
        max_size: int = 1600,
        overlap: int = 200,
        semantic_threshold: float = 0.35,
        use_semantic_break: bool = True,
    ) -> None:
        self.target_size = target_size or chunk_target()
        self.max_size = max_size or chunk_max()
        self.overlap = overlap or chunk_overlap()
        self.semantic_threshold = semantic_threshold
        self.use_semantic_break = use_semantic_break
        self._embedder: LocalEmbedder | None = None

    def _get_embedder(self) -> LocalEmbedder:
        """Retorna (e inicializa) o embedder local usado no refinamento semântico."""
        if self._embedder is None:
            self._embedder = LocalEmbedder()
        return self._embedder

    def _fit_embedder(self, texts: list[str]) -> None:
        """Ajusta o vocabulário do embedder local sobre o corpus de sentenças."""
        if self._embedder is None:
            self._embedder = LocalEmbedder()
        if not self._embedder._fitted:
            self._embedder.fit(texts)

    def chunk(self, text: str, parent_id: str, metadata: dict | None = None) -> list[TextChunk]:
        """Split a single document into semantic chunks."""
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        sentences = split_sentences(text)
        if not sentences:
            return []

        if self.use_semantic_break and len(sentences) > 2:
            self._fit_embedder(sentences)
            boundaries = self._find_breakpoints(sentences)
            groups = self._group_by_boundaries(sentences, boundaries)
        else:
            groups = self._group_by_size(sentences)

        chunks = []
        for i, group in enumerate(groups):
            if not group.strip():
                continue
            chunks.append(
                TextChunk(
                    text=group.strip(),
                    position=i,
                    parent_id=parent_id,
                    metadata={**metadata, "position": i, "parent_id": parent_id},
                )
            )

        return chunks

    def _group_by_size(self, sentences: list[str]) -> list[str]:
        """Simple size-based grouping with overlap."""
        groups = []
        current = ""
        for s in sentences:
            if len(current) + len(s) > self.target_size and current:
                groups.append(current)
                tail_words = current.split()[-self.overlap // 5:] if self.overlap > 0 else []
                current = " ".join(tail_words + [s]) if tail_words else s
            else:
                current = current + " " + s if current else s
        if current:
            groups.append(current)
        return groups

    def _find_breakpoints(self, sentences: list[str]) -> set[int]:
        """Find indices where semantic distance exceeds threshold."""
        embedder = self._get_embedder()
        vectors = embedder.embed_batch(sentences)
        breakpoints: set[int] = set()
        for i in range(1, len(vectors)):
            v1, v2 = vectors[i - 1], vectors[i]
            n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if n1 == 0 or n2 == 0:
                continue
            sim = float(np.dot(v1, v2) / (n1 * n2))
            dist = 1.0 - sim
            if dist > self.semantic_threshold:
                breakpoints.add(i)
        return breakpoints

    def _group_by_boundaries(self, sentences: list[str], breakpoints: set[int]) -> list[str]:
        """Group sentences by semantic breakpoints, respecting max size."""
        groups: list[str] = []
        current: list[str] = []
        for i, s in enumerate(sentences):
            current.append(s)
            too_long = sum(len(x) for x in current) > self.target_size
            at_break = (i + 1) in breakpoints
            too_max = sum(len(x) for x in current) > self.max_size
            if (at_break and too_long) or too_max:
                groups.append(" ".join(current))
                if self.overlap > 0 and len(current) > 1:
                    overlap_count = max(1, self.overlap // 50)
                    current = current[-overlap_count:]
                else:
                    current = []
        if current:
            groups.append(" ".join(current))
        return groups


def chunk_kb(
    chunker: SemanticChunker,
    items: list,
) -> list[tuple[object, TextChunk]]:
    """Apply the chunker to every NVIDIAChunk in a KB list.

    Returns list of (parent_chunk, text_chunk) tuples preserving parent metadata.
    """
    out: list[tuple[object, TextChunk]] = []
    for parent in items:
        children = chunker.chunk(
            parent.content,
            parent_id=parent.id,
            metadata={
                "tech": parent.tech,
                "category": parent.category,
                "title": parent.title,
                "url": parent.url,
                "tags": parent.tags,
            },
        )
        for c in children:
            out.append((parent, c))
    return out
