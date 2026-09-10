"""LLM helper — uses OpenRouter (multi-model) with smart fallbacks.

Per TAPI spec, multi-agent system uses LLM for reasoning. With limited API budget
during development, we use a hybrid approach:
- Simple keyword-based analysis for extraction/classification
- Optional LLM call for recommendation reasoning
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time

from loguru import logger

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "anthropic/claude-3-haiku")


class LLMClient:
    """OpenRouter multi-model client with smart fallback."""

    def __init__(self, model: str = MODEL) -> None:
        """Inicializa o cliente com o modelo OpenRouter e registra telemetria."""
        self.model = model
        self.api_key = OPENROUTER_API_KEY
        self._client = None
        # Telemetry per most recent call (token usage / latency). Nodes copy
        # these into AgentState.telemetry.node_token_usage after a call.
        self.last_usage: dict | None = None
        self.last_latency_ms: float | None = None

    def is_available(self) -> bool:
        """Indica se o LLM está habilitado (presença de OPENROUTER_API_KEY)."""
        return bool(self.api_key)

    def last_call_stats(self) -> dict:
        """Token usage + latency of the most recent LLM call."""
        return {
            "model": self.model,
            "prompt_tokens": (self.last_usage or {}).get("prompt_tokens", 0),
            "completion_tokens": (self.last_usage or {}).get("completion_tokens", 0),
            "total_tokens": (self.last_usage or {}).get("total_tokens", 0),
            "latency_ms": round(self.last_latency_ms or 0.0, 1),
        }

    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: dict | None = None,
    ) -> str:
        """Executa uma chamada de chat ao OpenRouter com retry exponencial (0s/1s/2s).

        Retorna a resposta textual bruta ou string vazia em falha. Apenas erros
        transitórios (408, 429, 5xx e falhas de rede/timeout) são reexecutados.
        Em caso de indisponibilidade, retorna "" para que os nós usem o fallback
        determinístico.
        """
        if not self.is_available():
            return ""
        self.last_usage = None
        self.last_latency_ms = None
        try:
            import httpx
            if not self._client:
                self._client = httpx.AsyncClient(timeout=60)
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                payload["response_format"] = response_format

            # Retry with exponential backoff (3 tentativas: 0s, 1s, 2s)
            delays = [0, 1, 2]
            last_status = None
            last_text = None
            last_exc: Exception | None = None
            for attempt, delay in enumerate(delays, 1):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    t0 = time.perf_counter()
                    r = await self._client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    self.last_latency_ms = (time.perf_counter() - t0) * 1000
                    last_status = r.status_code
                    last_text = r.text
                    if r.status_code == 200:
                        data = r.json()
                        self.last_usage = data.get("usage") or {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                        }
                        return data["choices"][0]["message"]["content"]
                    # Retry apenas em erros transientes (5xx, 408, 429)
                    if r.status_code not in (408, 429, 500, 502, 503, 504):
                        break
                    logger.warning(
                        f"LLM API transient error {r.status_code} "
                        f"(attempt {attempt}/3) — retrying in {delay}s"
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    last_exc = e
                    logger.warning(
                        f"LLM network error (attempt {attempt}/3): {e} — "
                        f"retrying in {delay}s"
                    )

            if last_exc:
                logger.error(f"LLM call failed after retries: {last_exc}")
            else:
                logger.warning(
                    f"LLM API error after retries: {last_status} {last_text[:200]}"
                )
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
        return ""

    async def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 3000,
    ) -> dict | list:
        """Chamada LLM com resposta parseada como JSON (tolerante a code blocks).

        Usada por nós que exigem saída estruturada (ex.: query_planner).
        Retorna dict/list vazio se o parse falhar.
        """
        raw = await self.complete(system, user, temperature, max_tokens)
        return _safe_parse_json(raw)


def _safe_parse_json(text: str):
    """Extract JSON from LLM response (handles code blocks)."""
    if not text:
        return {}
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Extract from code block
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Extract first {...} or [...]
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


llm = LLMClient()
