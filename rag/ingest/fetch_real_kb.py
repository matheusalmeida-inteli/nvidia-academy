"""Fetch real NVIDIA documentation content to enrich the KB.

Downloads official NVIDIA product pages, GitHub READMEs, and blog posts
to build a real knowledge base (not synthetic).
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
from loguru import logger
from trafilatura import extract

# Real NVIDIA documentation sources — verified to be accessible
NVIDIA_SOURCES = [
    # === Official product pages ===
    {
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
        "tech": "NVIDIA NIM",
        "category": "AI Microservices",
        "title": "NVIDIA NIM — Inference Microservices",
    },
    {
        "url": "https://developer.nvidia.com/nim",
        "tech": "NVIDIA NIM",
        "category": "Developer",
        "title": "NVIDIA NIM for Developers",
    },
    # === NeMo ===
    {
        "url": "https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
        "tech": "NVIDIA NeMo",
        "category": "LLM Framework",
        "title": "NeMo Framework",
    },
    {
        "url": "https://github.com/NVIDIA/NeMo",
        "tech": "NVIDIA NeMo",
        "category": "Open Source",
        "title": "NeMo GitHub Repository",
    },
    # === Triton ===
    {
        "url": "https://developer.nvidia.com/triton-inference-server",
        "tech": "NVIDIA Triton Inference Server",
        "category": "Inference Serving",
        "title": "Triton Inference Server",
    },
    {
        "url": "https://github.com/triton-inference-server/server",
        "tech": "NVIDIA Triton Inference Server",
        "category": "Open Source",
        "title": "Triton GitHub Repository",
    },
    # === TensorRT-LLM ===
    {
        "url": "https://github.com/NVIDIA/TensorRT-LLM",
        "tech": "TensorRT-LLM",
        "category": "LLM Optimization",
        "title": "TensorRT-LLM GitHub Repository",
    },
    # === RAPIDS ===
    {
        "url": "https://rapids.ai/",
        "tech": "NVIDIA RAPIDS",
        "category": "Data Science",
        "title": "RAPIDS — GPU-Accelerated Data Science",
    },
    {
        "url": "https://docs.rapids.ai/api/cudf/stable/",
        "tech": "cuDF",
        "category": "Data Processing",
        "title": "cuDF Documentation",
    },
    {
        "url": "https://docs.rapids.ai/api/cuml/stable/",
        "tech": "cuML",
        "category": "Machine Learning",
        "title": "cuML Documentation",
    },
    # === Riva ===
    {
        "url": "https://developer.nvidia.com/riva",
        "tech": "NVIDIA Riva",
        "category": "Speech AI",
        "title": "NVIDIA Riva Speech AI",
    },
    # === Omniverse ===
    {
        "url": "https://www.nvidia.com/en-us/omniverse/",
        "tech": "NVIDIA Omniverse",
        "category": "3D Platform",
        "title": "NVIDIA Omniverse Platform",
    },
    # === Isaac ===
    {
        "url": "https://developer.nvidia.com/isaac",
        "tech": "NVIDIA Isaac",
        "category": "Robotics",
        "title": "NVIDIA Isaac Robotics Platform",
    },
    {
        "url": "https://developer.nvidia.com/isaac/sim",
        "tech": "NVIDIA Isaac",
        "category": "Robotics Simulation",
        "title": "Isaac Sim",
    },
    # === Clara ===
    {
        "url": "https://www.nvidia.com/en-us/clara/",
        "tech": "NVIDIA Clara",
        "category": "Healthcare",
        "title": "NVIDIA Clara Healthcare Platform",
    },
    {
        "url": "https://github.com/Project-MONAI/MONAI",
        "tech": "MONAI",
        "category": "Medical Imaging",
        "title": "MONAI — Medical Open Network for AI",
    },
    # === Morpheus ===
    {
        "url": "https://developer.nvidia.com/morpheus-cybersecurity",
        "tech": "NVIDIA Morpheus",
        "category": "Cybersecurity",
        "title": "NVIDIA Morpheus Cybersecurity AI",
    },
    {
        "url": "https://github.com/nvidia/morpheus",
        "tech": "NVIDIA Morpheus",
        "category": "Open Source",
        "title": "Morpheus GitHub Repository",
    },
    # === AI Enterprise ===
    {
        "url": "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
        "tech": "NVIDIA AI Enterprise",
        "category": "Enterprise Platform",
        "title": "NVIDIA AI Enterprise",
    },
    # === CUDA ===
    {
        "url": "https://developer.nvidia.com/cuda-toolkit",
        "tech": "CUDA",
        "category": "GPU Computing",
        "title": "CUDA Toolkit",
    },
    {
        "url": "https://developer.nvidia.com/cudnn",
        "tech": "CUDA",
        "category": "GPU Libraries",
        "title": "cuDNN Deep Learning Library",
    },
    # === Inception ===
    {
        "url": "https://www.nvidia.com/en-us/startups/",
        "tech": "NVIDIA Inception",
        "category": "Startup Program",
        "title": "NVIDIA Inception Program",
    },
    # === NeMo Guardrails ===
    {
        "url": "https://github.com/NVIDIA/NeMo-Guardrails",
        "tech": "NeMo Guardrails",
        "category": "AI Safety",
        "title": "NeMo Guardrails GitHub",
    },
    # === API Catalog (TAPI §8.2) ===
    {
        "url": "https://build.nvidia.com/",
        "tech": "NVIDIA API Catalog",
        "category": "Model Hub",
        "title": "NVIDIA API Catalog — Models & Endpoints",
    },
    # === Triton docs (TAPI §8.2) ===
    {
        "url": "https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/",
        "tech": "NVIDIA Triton Inference Server",
        "category": "Documentation",
        "title": "Triton Inference Server Documentation",
    },
    # === AI services playbooks (TAPI §8.1) ===
    {
        "url": "https://sequoiacap.com/article/services-the-new-software/",
        "tech": "AI Services",
        "category": "Industry Trend",
        "title": "Sequoia — AI Services: The New Software",
    },
    {
        "url": "https://www.emcap.com/thoughts/the-ai-native-services-playbook",
        "tech": "AI Services",
        "category": "Industry Trend",
        "title": "Emergence — AI-Native Services Playbook",
    },
    {
        "url": "https://blogs.nvidia.com/blog/ai-5-layer-cake/",
        "tech": "AI Services",
        "category": "Industry Trend",
        "title": "NVIDIA AI 5-Layer Cake",
    },
    # === Extra NVIDIA docs ===
    {
        "url": "https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/",
        "tech": "NVIDIA Jetson",
        "category": "Edge AI",
        "title": "NVIDIA Jetson — Embedded AI",
    },
    {
        "url": "https://www.nvidia.com/en-us/gpu-cloud/",
        "tech": "NVIDIA NGC",
        "category": "GPU Cloud",
        "title": "NVIDIA NGC — GPU Cloud & Containers",
    },
    {
        "url": "https://developer.nvidia.com/tensorrt",
        "tech": "TensorRT",
        "category": "Inference Optimization",
        "title": "NVIDIA TensorRT — High-Performance Inference",
    },
    {
        "url": "https://docs.rapids.ai/api/cugraph/stable/",
        "tech": "cuGraph",
        "category": "Graph Analytics",
        "title": "cuGraph Documentation",
    },
    {
        "url": "https://docs.rapids.ai/api/cuspatial/stable/",
        "tech": "cuSpatial",
        "category": "Spatial Data",
        "title": "cuSpatial Documentation",
    },
    {
        "url": "https://developer.nvidia.com/flare",
        "tech": "NVIDIA FLARE",
        "category": "Federated Learning",
        "title": "NVIDIA FLARE — Federated Learning",
    },
    {
        "url": "https://developer.nvidia.com/deepstream-sdk",
        "tech": "DeepStream",
        "category": "Video Analytics",
        "title": "DeepStream SDK",
    },
    {
        "url": "https://developer.nvidia.com/tao",
        "tech": "NVIDIA TAO",
        "category": "Model Customization",
        "title": "NVIDIA TAO Toolkit",
    },
]


CACHE_DIR = Path("/tmp/nvidia_kb_cache")
REAL_KB_PATH = Path("/tmp/nvidia_real_kb.json")
MAX_CONTENT_CHARS = 60000


async def fetch_url(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch URL content with retries."""
    cache_file = CACHE_DIR / (re.sub(r"[^a-zA-Z0-9]", "_", url)[:200] + ".txt")
    if cache_file.exists():
        logger.debug(f"Cache hit: {url}")
        return cache_file.read_text(encoding="utf-8", errors="ignore")

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(3):
        try:
            response = await client.get(url, headers=headers, timeout=20.0, follow_redirects=True)
            if response.status_code == 200:
                text = extract(response.text, include_comments=False, include_tables=False, favor_recall=True)
                if text and len(text) > 200:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(text, encoding="utf-8")
                    logger.info(f"Fetched {url} ({len(text)} chars)")
                    return text
            logger.warning(f"Status {response.status_code} for {url}")
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            await asyncio.sleep(2)
    return None


async def fetch_all_real_kb() -> list[dict]:
    """Fetch all real NVIDIA documentation pages."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        results = []
        for source in NVIDIA_SOURCES:
            text = await fetch_url(client, source["url"])
            if text:
                content = text if len(text) <= MAX_CONTENT_CHARS else text[:MAX_CONTENT_CHARS]
                results.append({
                    "tech": source["tech"],
                    "category": source["category"],
                    "title": source["title"],
                    "url": source["url"],
                    "content": content,
                })
            else:
                logger.error(f"Failed to fetch: {source['url']}")
    REAL_KB_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Fetched {len(results)}/{len(NVIDIA_SOURCES)} pages → wrote {REAL_KB_PATH}")
    return results


if __name__ == "__main__":
    results = asyncio.run(fetch_all_real_kb())
    print(f"Got {len(results)} real KB entries")
    for r in results[:3]:
        print(f"  {r['tech']}: {r['content'][:100]}...")
