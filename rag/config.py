"""Configuração centralizada do RAG — fonte única de verdade das variáveis RAG_*.

Todos os knobs (chunking, retrieval, rerank) são lidos aqui, a partir de
variáveis de ambiente com defaults canônicos. Assim, `chunker`, `ingestor`,
`retriever` e `eval` compartilham os mesmos valores — eliminando divergências
como o `NVIDIAIngestor` usando 400/800 enquanto o `shared.py` usava 800/1600.

As funções leem do ambiente a cada chamada, preservando a possibilidade de
override em runtime (ex.: `RAG_RERANK=0` no eval A/B).
"""
from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "1" if default else "0")
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------
def semantic_chunking() -> bool:
    """True se o chunking semântico está ativo (RAG_SEMANTIC_CHUNKING)."""
    return _env_bool("RAG_SEMANTIC_CHUNKING", True)


def chunk_target() -> int:
    """Tamanho-alvo do chunk em caracteres (RAG_CHUNK_TARGET)."""
    return _env_int("RAG_CHUNK_TARGET", 800)


def chunk_max() -> int:
    """Tamanho máximo do chunk em caracteres (RAG_CHUNK_MAX)."""
    return _env_int("RAG_CHUNK_MAX", 1600)


def chunk_overlap() -> int:
    """Sobreposição entre chunks em caracteres (RAG_CHUNK_OVERLAP)."""
    return _env_int("RAG_CHUNK_OVERLAP", 200)


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------
def top_k_dense() -> int:
    """Número de candidatos densos antes do RRF (RAG_TOP_K_DENSE)."""
    return _env_int("RAG_TOP_K_DENSE", 20)


def top_k_sparse() -> int:
    """Número de candidatos BM25 antes do RRF (RAG_TOP_K_SPARSE)."""
    return _env_int("RAG_TOP_K_SPARSE", 20)


def top_k_rerank() -> int:
    """Número de resultados finais após o rerank (RAG_TOP_K_RERANK)."""
    return _env_int("RAG_TOP_K_RERANK", 3)


def rrf_k() -> int:
    """Constante k da fusão RRF (RAG_RRF_K)."""
    return _env_int("RAG_RRF_K", 55)


def rrf_cap() -> int:
    """Cap de candidatos pós-RRF (RAG_RRF_CAP)."""
    return _env_int("RAG_RRF_CAP", 20)


def rrf_dense_weight() -> float:
    """Peso da fonte densa no RRF (RAG_RRF_DENSE_WEIGHT)."""
    return _env_float("RAG_RRF_DENSE_WEIGHT", 1.0)


def rrf_sparse_weight() -> float:
    """Peso da fonte esparsa no RRF (RAG_RRF_SPARSE_WEIGHT)."""
    return _env_float("RAG_RRF_SPARSE_WEIGHT", 1.0)


def category_boost() -> float:
    """Bonus soft de categoria/metadata por chunk (RAG_CATEGORY_BOOST)."""
    return _env_float("RAG_CATEGORY_BOOST", 0.5)


def rerank_enabled() -> bool:
    """True se o rerank está ativo (RAG_RERANK=1). RAG_RERANK=0 desabilita."""
    return _env_bool("RAG_RERANK", True)


def mmr_enabled() -> bool:
    """True se o reranker MMR (diversidade) está ativo (RAG_MMR=1)."""
    return _env_bool("RAG_MMR", False)


def mmr_lambda() -> float:
    """Lambda do MMR (RAG_MMR_LAMBDA): peso relevância vs diversidade."""
    return _env_float("RAG_MMR_LAMBDA", 0.7)


def query_rewrite_enabled() -> bool:
    """True se o rewrite de query via LLM está ativo (RAG_QUERY_REWRITE=1)."""
    return _env_bool("RAG_QUERY_REWRITE", False)


def local_dense_fallback() -> bool:
    """True se a busca densa local (sem Qdrant) é usada como fallback.

    Quando o Qdrant está fora do ar ou há descasamento de dimensão, tenta
    recuperar por cosseno contra os chunks embutidos localmente antes de
    abandonar completamente a fonte densa (RAG_LOCAL_DENSE_FALLBACK).
    """
    return _env_bool("RAG_LOCAL_DENSE_FALLBACK", True)


def rag_synthesize_enabled() -> bool:
    """True se a síntese de justificativa via LLM com citações está ativa.

    TAPI §5.3 (8) 'Geração da resposta com citações': quando habilitado e há
    LLM disponível, a justificativa técnica de recomendações ancoradas em RAG é
    sintetizada por LLM citando as fontes recuperadas. Sem LLM/fontes, o
    sistema mantém a justificativa determinística (reference card).
    (RAG_SYNTHESIZE=1 default; RAG_SYNTHESIZE=0 desabilita.)
    """
    return _env_bool("RAG_SYNTHESIZE", True)




