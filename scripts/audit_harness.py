"""Audit harness — executa o pipeline e armazena as saídas em /tmp/audit_runs.jsonl.

Uso:
    /home/misareverberate/.pixi/bin/pixi run python scripts/audit_harness.py
"""
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

API_URL = "http://localhost:8000/query"
OUT = Path("/tmp/audit_runs.jsonl")

# Cenários: cobre diferentes padrões de busca, setores, e estilos de pergunta.
SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "A1_fintech_native",
        "query": "startups AI-native de fintech com dados próprios",
        "max_startups": 6,
    },
    {
        "id": "A2_health_imaging",
        "query": "startups de saúde com modelos de imagem médica próprios",
        "max_startups": 6,
    },
    {
        "id": "A3_logistics",
        "query": "AI-native startups no setor de logística com gap GPU",
        "max_startups": 6,
    },
    {
        "id": "A4_wrapper_defense",
        "query": "startups com defensibilidade real (não wrappers de LLM)",
        "max_startups": 8,
    },
    {
        "id": "A5_agtech",
        "query": "agtech com modelos de recomendação e dados agrícolas",
        "max_startups": 6,
    },
    {
        "id": "A6_retail",
        "query": "varejo e e-commerce com personalização por IA",
        "max_startups": 6,
    },
    {
        "id": "A7_robotics",
        "query": "robótica e automação industrial com simulação",
        "max_startups": 6,
    },
    {
        "id": "A8_cybersec",
        "query": "cibersegurança e detecção de fraude em tempo real",
        "max_startups": 6,
    },
    {
        "id": "A9_inception_fit",
        "query": "alto fit para Inception Brasil com NVIDIA NIM",
        "max_startups": 8,
    },
    {
        "id": "A10_specific",
        "query": "Huna e Dasa saúde IA",
        "max_startups": 4,
    },
]


async def run_scenario(client: httpx.AsyncClient, scenario: dict) -> dict:
    try:
        r = await client.post(API_URL, json=scenario, timeout=120.0)
        if r.status_code != 200:
            return {"scenario": scenario, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
        data = r.json()
        return {"scenario": scenario, "result": data}
    except Exception as e:
        return {"scenario": scenario, "error": str(e)}


async def main() -> None:
    OUT.unlink(missing_ok=True)
    async with httpx.AsyncClient() as client:
        for s in SCENARIOS:
            print(f"→ {s['id']}: {s['query']}", flush=True)
            r = await run_scenario(client, s)
            with OUT.open("a") as f:
                f.write(json.dumps(r, default=str) + "\n")
            if "error" in r:
                print(f"  ❌ {r['error']}")
            else:
                res = r["result"]
                print(
                    f"  ✓ {len(res.get('startups', []))} startups, "
                    f"briefing={res.get('briefing') is not None}, "
                    f"total={res.get('total_found', 0)}"
                )
    print(f"\n→ Saved to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
