"""Lightweight JSONL telemetry sink (no external dependencies).

Persists one JSON line per pipeline run to logs/telemetry-YYYYMMDD.ndjson.
This is the primary evidence store behind "Ação 3": node timings, LLM token
usage, rerank score deltas and evidence reasons feed the latency/cost/quality
decisions. Optional LangSmith push can be added later if a key is configured.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

LOGS_DIR = Path(os.environ.get("RAG_TELEMETRY_DIR", "logs"))


def _get(obj, key: str, default=None):
    """Access a field on a dict (LangGraph output) or dataclass uniformly."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _node_tokens(tel) -> dict:
    """Resume o uso de tokens por nó em formato serializável para NDJSON."""
    usage = _get(tel, "node_token_usage", {}) or {}
    return {
        node: {
            "model": stats.get("model", ""),
            "prompt_tokens": stats.get("prompt_tokens", 0),
            "completion_tokens": stats.get("completion_tokens", 0),
            "latency_ms": round(stats.get("latency_ms", 0), 1),
        }
        for node, stats in usage.items()
    }


def _to_record(state) -> dict:
    """Converte o estado final da pipeline em um registro plano de telemetria."""
    tel = _get(state, "telemetry")
    return {
        "run_id": _get(tel, "run_id", ""),
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "runtime_seconds": round(
            max(0.0, (_get(tel, "ended_at", 0.0) or 0.0) - (_get(tel, "started_at", 0.0) or 0.0)),
            3,
        ),
        "user_query": _get(state, "user_query", ""),
        "node_timings_ms": {k: round(v, 1) for k, v in (_get(tel, "node_timings", {}) or {}).items()},
        "node_counts": dict(_get(tel, "node_counts", {}) or {}),
        "node_token_usage": _node_tokens(tel),
        "retrieval_scores_pre_rerank": dict(_get(tel, "retrieval_scores_pre_rerank", {}) or {}),
        "retrieval_scores_post_rerank": dict(_get(tel, "retrieval_scores_post_rerank", {}) or {}),
        "rerank_effectiveness": dict(_get(tel, "rerank_effectiveness", {}) or {}),
        "evidence_reasons": dict(_get(tel, "evidence_reasons", {}) or {}),
        "low_evidence": bool(_get(tel, "low_evidence", False)),
        "supervisor_actions": list(_get(state, "supervisor_actions", []) or []),
        "n_startups": len(_get(state, "retrieved_startups", []) or []),
        "n_recommendations": len(_get(state, "recommendations", []) or []),
        "errors": list(_get(state, "errors", []) or []),
    }


class TelemetrySink:
    """Appends one JSON line per run to a date-partitioned NDJSON file."""

    def __init__(self, logs_dir: Path | str = LOGS_DIR) -> None:
        """Configura o diretório de destino dos arquivos de telemetria."""
        self.logs_dir = Path(logs_dir)

    def _path(self) -> Path:
        """Caminho do arquivo NDJSON diário (logs/telemetry-YYYYMMDD.ndjson)."""
        return self.logs_dir / f"telemetry-{datetime.now(UTC):%Y%m%d}.ndjson"

    async def submit(self, record: dict) -> None:
        """Apendam uma linha JSON por execução; falhas de escrita são toleradas."""
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            with open(self._path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[telemetry] failed to write run record: {e}")


async def submit_result(state) -> None:
    """Build + persist the telemetry record for a pipeline result (dict or AgentState)."""
    try:
        await TelemetrySink().submit(_to_record(state))
    except Exception as e:
        logger.warning(f"[telemetry] failed to write run record: {e}")
