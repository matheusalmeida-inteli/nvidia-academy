"""NVIDIA knowledge base — real + synthetic content for RAG ingestion.

Real content is fetched from NVIDIA official documentation via fetch_real_kb.py
and cached in /tmp/nvidia_kb_cache/. Synthetic content is used as fallback.

Each entry maps to a chunk in Qdrant.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class NVIDIAChunk:
    """Fragmento da base de conhecimento NVIDIA (tecnologia, categoria, conteúdo e fonte)."""
    id: str
    tech: str
    category: str
    title: str
    content: str
    url: str
    tags: list[str] = field(default_factory=list)


NVIDIA_KB: list[NVIDIAChunk] = []
_KB_LOADED = False
_LOADING_REAL = False
_LOADING_JSON = False

_REAL_CACHE_PATH = Path("/tmp/nvidia_real_kb.json")
# Dataset curado versionado no repo: permite editar a KB sem mexer no código.
_JSONL_PATH = Path(__file__).resolve().parent / "data" / "nvidia_concepts.jsonl"


def _add(
    tech: str,
    category: str,
    title: str,
    content: str,
    url: str,
    tags: list[str] | None = None,
) -> None:
    """Adiciona um chunk curado à KB; suprimido no modo 'real' ou 'jsonl' presente."""
    # Synthetic entries are defined at module level below. When a real KB
    # cache OR the curated JSONL dataset exists, those module-level calls are
    # suppressed so the KB is not duplicated ("real only" / "jsonl" mode).
    # _load_real_kb()/_load_json_kb() set their flags so their entries are
    # always added even when the external source is present.
    if not _LOADING_REAL and not _LOADING_JSON and _external_source_exists():
        return
    chunk_id = f"nvidia_{tech.lower().replace(' ', '_').replace('-', '_')}_{len(NVIDIA_KB)}"
    NVIDIA_KB.append(NVIDIAChunk(
        id=chunk_id,
        tech=tech,
        category=category,
        title=title,
        content=content,
        url=url,
        tags=tags or [],
    ))


def _external_source_exists() -> bool:
    """True se há um cache real ou dataset JSONL disponível (supressão sintética)."""
    return _REAL_CACHE_PATH.exists() or _JSONL_PATH.exists()


def _load_real_kb() -> None:
    """Load real NVIDIA documentation from cached JSON."""
    global _LOADING_REAL
    cache_path = _REAL_CACHE_PATH
    if not cache_path.exists():
        return
    _LOADING_REAL = True
    try:
        with open(cache_path, encoding="utf-8") as f:
            entries = json.load(f)
        for entry in entries:
            _add(
                tech=entry["tech"],
                category=entry["category"],
                title=entry["title"],
                content=entry["content"],
                url=entry["url"],
            )
    except Exception as e:
        import warnings
        warnings.warn(f"Failed to load real KB: {e}", stacklevel=2)
    finally:
        _LOADING_REAL = False


def _load_json_kb() -> None:
    """Load curated KB from rag/ingest/data/nvidia_concepts.jsonl.

    Prioridade: cache real (/tmp) > JSONL > sintético embutido no módulo.
    """
    global _LOADING_JSON
    if not _JSONL_PATH.exists():
        return
    _LOADING_JSON = True
    try:
        with open(_JSONL_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                NVIDIA_KB.append(NVIDIAChunk(
                    id=entry["id"],
                    tech=entry["tech"],
                    category=entry["category"],
                    title=entry["title"],
                    content=entry["content"],
                    url=entry.get("url", ""),
                    tags=entry.get("tags", []) or [],
                ))
        logger.info(f"Loaded {len(NVIDIA_KB)} curated concepts from {_JSONL_PATH.name}")
    except Exception as e:
        import warnings
        warnings.warn(f"Failed to load curated JSONL KB: {e}", stacklevel=2)
        NVIDIA_KB.clear()
    finally:
        _LOADING_JSON = False


def _ensure_kb() -> None:
    """Garante a KB carregada uma única vez por processo (real > JSONL > sintética)."""
    global _KB_LOADED
    if _KB_LOADED:
        return
    _KB_LOADED = True
    _load_real_kb()
    if NVIDIA_KB:
        return
    _load_json_kb()
    if NVIDIA_KB:
        return
    _load_synthetic_kb()



def _load_synthetic_kb() -> None:
    """Load synthetic KB (fallback when real content unavailable)."""
# === NVIDIA Inception ===
_add(
    tech="NVIDIA Inception",
    category="Program",
    title="NVIDIA Inception Overview",
    content="""NVIDIA Inception is a free GPU-accelerated program designed to help startups cutting-edge AI and data science startups grow faster. The program provides startups with access to technology, expertise, and a global community of innovators. Key benefits include: GPU cloud credits (up to $100K), NVIDIA Deep Learning Institute training, technical support from NVIDIA engineers, go-to-market support and co-marketing, access to NVIDIA's global investor network, and connections to enterprise customers through the NVIDIA Inception Premier Program. The program is designed for companies at all stages, from pre-seed to Series D and beyond. Inception members get access to NVIDIA's cutting-edge platform including NIM microservices, NeMo for LLM customization, Triton Inference Server for production deployment, and TensorRT-LLM for optimized inference. The program also provides mentorship from NVIDIA experts and introductions to potential investors and partners through the Inception Capital Connect program.""",
    url="https://www.nvidia.com/en-us/startups/",
    tags=["startup program", "credits", "GPU", "mentorship", "go-to-market"],
)

_add(
    tech="NVIDIA Inception",
    category="Benefits",
    title="Inception Benefits by Stage",
    content="""NVIDIA Inception benefits scale with startup stage. Pre-seed and seed stage startups receive: free GPU cloud credits up to $50K, access to NVIDIA NGC container registry with pre-trained models, technical training from Deep Learning Institute, access to Inception community and events, and marketing support. Series A startups get: up to $100K in GPU credits, direct access to NVIDIA solution architects for technical guidance, co-marketing opportunities, introductions to enterprise customers, and priority access to new NVIDIA products. Series B+ startups receive the most comprehensive support including dedicated NVIDIA account manager, enterprise customer introductions, investment facilitation through Inception Capital, and potential inclusion in NVIDIA's product roadmap discussions. All members get access to the Inception online portal, webinars, office hours with NVIDIA experts, and the annual Inception Innovation Showcase event.""",
    url="https://www.nvidia.com/en-us/startups/",
    tags=["credits", "cloud", "GPU credits", "enterprise", "mentorship"],
)

# === NVIDIA NIM ===
_add(
    tech="NVIDIA NIM",
    category="AI Microservices",
    title="NVIDIA NIM Overview",
    content="""NVIDIA NIM (NVIDIA Inference Microservices) is a set of easy-to-use pre-built containers for deploying AI models at scale. NIM provides optimized inference for the world's most popular AI models including Llama 3, Mistral, Mixtral, Stable Diffusion, and specialized models for healthcare, manufacturing, and retail. Each NIM microservice is pre-optimized with TensorRT and TensorRT-LLM, delivering up to 5x faster inference compared to raw deployment. NIM microservices expose a simple API compatible with OpenAI SDK, making it trivial to migrate existing LLM applications. Key use cases: chatbots and virtual assistants, code generation and completion, document summarization and Q&A, image generation and editing, speech and audio processing, and drug discovery. NIM runs on NVIDIA GPUs from RTX to H100 and can be deployed on-premises, in the cloud, or at the edge. Pricing is consumption-based with per-token and per-GPU-hour models.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
    tags=["inference", "microservices", "LLM", "deployment", "optimized", "TensorRT"],
)

_add(
    tech="NVIDIA NIM",
    category="Use Cases",
    title="NIM for Enterprise AI Applications",
    content="""NVIDIA NIM enables enterprises to deploy AI models in production with performance and reliability requirements. For RAG (Retrieval Augmented Generation) applications, NIM provides optimized inference for embedding models and LLMs, enabling low-latency responses. For customer service chatbots, NIM powers conversational AI with Llama 3 and Mistral models with sub-second latency. For code generation, NIM supports Code Llama and StarCoder for IDE integrations. For document intelligence, NIM accelerates OCR, layout understanding, and summarization. For healthcare, specialized NIMs for medical imaging, drug discovery (MolMIM), and clinical text processing are available. For manufacturing, NIM supports vision models for quality inspection and predictive maintenance. NIM can be deployed via Docker containers on any NVIDIA GPU infrastructure, in Kubernetes clusters, or through managed cloud services. The OpenAI-compatible API means existing LangChain, LlamaIndex, and other LLM frameworks work out of the box.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
    tags=["RAG", "chatbots", "code generation", "healthcare", "manufacturing", "LangChain"],
)

# === NVIDIA NeMo ===
_add(
    tech="NVIDIA NeMo",
    category="LLM Training",
    title="NeMo Framework Overview",
    content="""NVIDIA NeMo is an end-to-end platform for building, customizing, and deploying generative AI models. NeMo provides tools for: LLM pretraining from scratch, LLM fine-tuning with techniques like LoRA, QLoRA, and full-parameter fine-tuning, RLHF (Reinforcement Learning from Human Feedback) for alignment, evaluation with automated benchmarks, and guardrails for safe AI behavior. NeMo supports models from 1B to 405B parameters including Llama, Mistral, Mixtral, Gemma, Granite, and Nemotron. For training, NeMo uses tensor parallelism, pipeline parallelism, and data parallelism for efficient multi-GPU and multi-node training. NeMo Curator handles data processing, deduplication, and quality filtering at scale using RAPIDS and Dask. NeMo Aligner provides RLHF, DPO (Direct Preference Optimization), and RLAIF implementations. NeMo Evaluator offers automated evaluation on 50+ benchmarks. NeMo is available as open source on GitHub and through NGC containers pre-configured for training on NVIDIA GPUs.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
    tags=["fine-tuning", "RLHF", "training", "LLM", "customization", "alignment"],
)

_add(
    tech="NeMo Guardrails",
    category="AI Safety",
    title="NeMo Guardrails — Safe AI Systems",
    content="""NeMo Guardrails is an open-source toolkit for adding programmable guardrails to AI assistants and agents. Guardrails ensure AI systems behave according to organizational policies and safety guidelines. NeMo Guardrails supports: topical guardrails (keeping conversations on-topic), safety guardrails (blocking harmful content, PII leakage, jailbreaks), security guardrails (preventing prompt injection and data exfiltration), and custom rails defined in a simple DSL (Domain Specific Language). The Colang language allows defining conversational flows, validation rules, and fallback behaviors. Guardrails can intercept and modify user inputs and model outputs before they reach the application. Integration with LangChain, LlamaIndex, and any LLM via LangChain integration. NeMo Guardrails is particularly important for enterprise deployments where compliance, data governance, and responsible AI are requirements. The toolkit is production-ready and used by Fortune 500 companies for customer-facing AI applications.""",
    url="https://github.com/NVIDIA/NeMo-Guardrails",
    tags=["safety", "guardrails", "LLM", "security", "enterprise", "Colang", "LangChain"],
)

# === NVIDIA Triton ===
_add(
    tech="NVIDIA Triton Inference Server",
    category="Inference Serving",
    title="Triton Overview and Architecture",
    content="""NVIDIA Triton Inference Server is an open-source inference serving software that simplifies AI model deployment in production. Triton supports all major ML frameworks (PyTorch, TensorFlow, ONNX, Python, TensorRT) and model formats, enabling teams to deploy any model without rewriting. Key features: dynamic batching for throughput optimization, model concurrency for efficient GPU utilization, model pipelines and ensembles for multi-stage inference, streaming inference for real-time applications, automatic model versioning and A/B testing, and metrics via Prometheus for observability. Triton can serve models from cloud data centers to edge devices including NVIDIA Jetson. For LLM inference, Triton with TensorRT-LLM provides optimized batching, paged attention, and speculative decoding. Triton integrates with Kubernetes via Helm charts and KServe for enterprise MLOps. REST and gRPC APIs are provided. Triton Analyzer helps identify bottlenecks and optimize model configurations.""",
    url="https://developer.nvidia.com/triton-inference-server",
    tags=["serving", "production", "TensorRT", "PyTorch", "TensorFlow", "Kubernetes", "ONNX"],
)

# === TensorRT-LLM ===
_add(
    tech="TensorRT-LLM",
    category="LLM Optimization",
    title="TensorRT-LLM for Optimized LLM Inference",
    content="""TensorRT-LLM is NVIDIA's solution for high-performance LLM inference, delivering up to 4x throughput improvement over naive deployment. Key optimizations: custom attention kernels (Flash Attention 2), in-flight batching with dynamic sequence lengths, paged attention for efficient KV-cache management, speculative decoding for faster token generation, INT4/INT8/FP8 quantization with minimal accuracy loss, tensor parallelism for multi-GPU serving, and continuous batching for optimal GPU utilization. TensorRT-LLM supports Llama 2/3, Mistral, Mixtral, Gemma, Phi, Stable Diffusion, and Code Llama. It provides a Python API for building optimized engines and a Triton backend for production serving. For latency-critical applications, TensorRT-LLM enables sub-100ms time-to-first-token for 70B parameter models on 8xH100. The NVIDIA AI Enterprise license is required for production deployment. Open-source for research and development.""",
    url="https://github.com/NVIDIA/TensorRT-LLM",
    tags=["inference", "optimization", "LLM", "quantization", "batching", "H100", "A100"],
)

# === NVIDIA RAPIDS ===
_add(
    tech="NVIDIA RAPIDS",
    category="Data Science",
    title="RAPIDS Suite Overview",
    content="""NVIDIA RAPIDS is an open-source suite of libraries for GPU-accelerated data science and analytics. RAPIDS enables end-to-end GPU acceleration for the entire data science pipeline: data loading (cuDF), preprocessing (cuDF), feature engineering, model training (cuML), and model inference. RAPIDS cuDF provides a GPU DataFrame API compatible with pandas, delivering 10-100x speedups for data manipulation operations. cuML offers GPU-accelerated implementations of 100+ ML algorithms including clustering, dimensionality reduction, time series, and classical ML models. cuDF supports ETL operations, joins, groupby aggregations, and string operations all on GPU. RAPIDS integrates seamlessly with scikit-learn, pandas, and PyTorch via cuPy's GPU arrays. For large-scale data processing, Dask and Spark integration enables distributed GPU computing across clusters. RAPIDS is particularly relevant for startups processing large datasets, building recommendation systems, fraud detection, or real-time analytics dashboards.""",
    url="https://rapids.ai/",
    tags=["data science", "GPU", "cuDF", "cuML", "pandas", "sklearn", "machine learning"],
)

_add(
    tech="cuDF",
    category="Data Processing",
    title="cuDF — GPU DataFrame",
    content="""cuDF is a GPU DataFrame library that provides a pandas-like API for manipulating data on NVIDIA GPUs. cuDF accelerates common DataFrame operations by 10-100x compared to pandas on CPU. Key capabilities: reading/writing CSV, Parquet, ORC, and JSON with cuIO, filtering, grouping, joins, and aggregations on GPU, string operations with cuDF Strings, time series functionality, and multi-GPU support via Dask. Use cases: data preprocessing for ML pipelines, feature engineering at scale, exploratory data analysis on large datasets, ETL operations in data pipelines, and real-time analytics. cuDF integrates with cuML for zero-copy GPU ML training, with Dask for distributed processing, and with PyArrow for interoperability with Python data ecosystem.""",
    url="https://docs.rapids.ai/api/cudf/stable/",
    tags=["DataFrame", "pandas", "ETL", "preprocessing", "GPU", "data engineering"],
)

_add(
    tech="cuML",
    category="Machine Learning",
    title="cuML — GPU-Accelerated Machine Learning",
    content="""cuML provides GPU-accelerated machine learning algorithms that work directly on cuDF DataFrames. cuML includes 100+ algorithms covering: clustering (KMeans, DBSCAN, HDBSCAN), dimensionality reduction (PCA, UMAP, TSNE), regression and classification (RandomForest, KNN, SGD), time series (ARIMA, Kalman filters), and ensemble methods. For startups building recommendation systems, fraud detection, or predictive analytics, cuML enables training on millions of rows in seconds rather than hours. cuML's nearest neighbors implementations are 100x faster than scikit-learn for large-scale similarity search. cuML integrates with RAPIDS ecosystem and provides a scikit-learn-like API, enabling drop-in GPU acceleration for existing Python code with minimal changes.""",
    url="https://docs.rapids.ai/api/cuml/stable/",
    tags=["machine learning", "sklearn", "clustering", "regression", "recommendation", "fraud"],
)

# === NVIDIA Riva ===
_add(
    tech="NVIDIA Riva",
    category="Speech AI",
    title="Riva — Real-Time Speech AI",
    content="""NVIDIA Riva is a GPU-accelerated SDK for building real-time speech AI applications. Riva provides: automatic speech recognition (ASR) with streaming and batch modes supporting 10+ languages including Portuguese (Brazilian), text-to-speech (TTS) with neural voice synthesis in 30+ languages, and live captioning and translation. Riva's ASR achieves world-class accuracy with WER (Word Error Rate) below 3% on benchmark datasets. TTS provides natural-sounding voices with prosody control and speaker customization. Riva can be deployed on-premises, in the cloud, or at the edge on NVIDIA Jetson. Key APIs: HTTP/REST for batch and gRPC for streaming. Riva is available as containers with pre-trained models ready to use or for fine-tuning on domain-specific data. Use cases: voice assistants, call center transcription, meeting summarization, accessibility tools, and voice-controlled applications.""",
    url="https://developer.nvidia.com/riva",
    tags=["ASR", "TTS", "speech", "voice", "Portuguese", "Brazil", "streaming"],
)

# === NVIDIA Omniverse ===
_add(
    tech="NVIDIA Omniverse",
    category="Simulation & 3D",
    title="Omniverse Overview",
    content="""NVIDIA Omniverse is a platform for 3D design collaboration and simulation. Omniverse enables real-time physically accurate rendering, simulation, and collaboration for teams using different tools (AutoCAD, Blender, Maya, Revit, etc.). Key components: Omniverse Nucleus for real-time collaboration, Omniverse Kit for building extensions and applications, Omniverse Create for 3D artists, Omniverse View for reviewing and markup, and Omniverse Simulation for physics-based digital twins. For industrial AI, Omniverse enables: digital twins of factories, synthetic data generation for training computer vision models, real-time robot simulation with Isaac Sim, and urban planning with Earth-2. Omniverse supports USD (Universal Scene Description) as the open standard for 3D content. NVIDIA RTX GPUs provide real-time path tracing for photorealistic rendering. Enterprise licensing includes technical support and access to NVIDIA's professional services.""",
    url="https://www.nvidia.com/en-us/omniverse/",
    tags=["3D", "simulation", "digital twin", "robotics", "USD", "collaboration", "synthetic data"],
)

# === NVIDIA Isaac ===
_add(
    tech="NVIDIA Isaac",
    category="Robotics",
    title="Isaac Robotics Platform",
    content="""NVIDIA Isaac is a platform for developing, simulating, and deploying autonomous machines. Key components: Isaac Sim — physics-based robot simulation on Omniverse with accurate sensor models, Isaac ROS — ROS2 packages optimized for NVIDIA Jetson, Isaac Manipulator — for autonomous manipulation with contact-rich tasks, Isaac AMR — for autonomous mobile robots with fleet management, Isaac Perceptor — for 3D scene perception using vision AI, and Isaac Lab — for training robot policies with reinforcement learning. Isaac benefits: photorealistic simulation reduces real-world testing costs, GPU-accelerated perception enables real-time inference, synthetic data generation addresses the data scarcity problem, and end-to-end platform from simulation to edge deployment. Use cases: warehouse automation, manufacturing robots, delivery robots, agricultural robots and precision farming drones, and inspection drones. Jetson Orin provides the edge AI compute for deployed robots.""",
    url="https://developer.nvidia.com/isaac",
    tags=["robotics", "simulation", "AMR", "Jetson", "ROS", "reinforcement learning", "agriculture", "farming", "precision agriculture"],
)

_add(
    tech="RAPIDS",
    category="Data Science",
    title="RAPIDS for Agriculture and IoT Data",
    content="""NVIDIA RAPIDS accelerates data processing and ML for agriculture technology applications. cuDF provides GPU-accelerated DataFrame operations that process sensor data, satellite imagery, and weather data 10-100x faster than pandas. cuML includes GPU-accelerated algorithms for crop yield prediction, disease detection, soil analysis, and resource optimization. For precision agriculture: processing multispectral and hyperspectral imagery from drones and satellites on GPU; real-time analytics on edge devices (Jetson) for irrigation and pest control decisions; predictive models for harvest timing and market forecasting. RAPIDS integrates with Apache Arrow, Dask, and cuSpatial for geospatial analysis. AgTech startups use RAPIDS to process terabytes of field data in minutes instead of hours, enabling data-driven decisions at scale. The combination of RAPIDS for data processing, cuML for predictive models, and Isaac for robotics provides a complete GPU-accelerated stack for agricultural AI applications.""",
    url="https://rapids.ai/",
    tags=["agriculture", "IoT", "precision farming", "drones", "satellite imagery", "cuML", "cuDF"],
)

# === NVIDIA Clara ===
_add(
    tech="NVIDIA Clara",
    category="Healthcare",
    title="Clara Healthcare AI Platform",
    content="""NVIDIA Clara is a healthcare AI platform covering imaging, genomics, and drug discovery. Key products: Clara Guardian for healthcare facility analytics (body cameras, fall detection, patient monitoring), Clara Imaging for AI-assisted medical imaging (CT, MRI, X-ray analysis), MONAI as the open-source medical imaging AI framework (MONAI is now part of Clara), Clara Deploy for deploying AI models in clinical workflows, Clara Discovery for drug discovery including AlphaFold integration and molecular dynamics simulation, and Clara Holoscan for medical devices at the edge. Clara Holoscan powers real-time AI in surgical systems, endoscopy, and point-of-care devices. MONAI provides domain-specific data loading, preprocessing, and model architectures for medical imaging. Healthcare startups benefit from: GPU-accelerated training for medical AI models, certified deployment on Clara Enterprise for hospital environments, synthetic medical data generation for training, and integration with PACS and DICOM systems.""",
    url="https://www.nvidia.com/en-us/clara/",
    tags=["healthcare", "medical imaging", "MONAI", "drug discovery", "genomics", "HIPAA"],
)

# === NVIDIA Morpheus ===
_add(
    tech="NVIDIA Morpheus",
    category="Cybersecurity",
    title="Morpheus — AI-Powered Cybersecurity",
    content="""NVIDIA Morpheus is an open-source AI framework for cybersecurity that enables real-time detection of threats and anomalies. Morpheus provides: ML pipelines for processing network telemetry at scale, pre-trained models for phishing detection, ransomware identification, and anomaly detection, a drag-and-drop interface for building custom detection pipelines, and GPU-accelerated inference for sub-millisecond threat detection. Morpheus can ingest data from SIEMs (Splunk, Elastic), network taps, cloud logs (AWS CloudTrail, Azure, GCP), and endpoint agents. Use cases: detecting insider threats, identifying compromised accounts, fraud detection, API abuse prevention, and security operations center (SOC) automation. Morpheus + RAPIDS enables processing billions of events per day for real-time threat detection. Morpheus integrates with Kafka for streaming data and with NVIDIA BlueField DPUs for inline acceleration.""",
    url="https://developer.nvidia.com/morpheus-cybersecurity",
    tags=["cybersecurity", "threat detection", "anomaly", "fraud", "SIEM", "streaming"],
)

# === NVIDIA AI Enterprise ===
_add(
    tech="NVIDIA AI Enterprise",
    category="Enterprise Platform",
    title="NVIDIA AI Enterprise Overview",
    content="""NVIDIA AI Enterprise is the enterprise-grade software platform for production AI. It includes: optimized versions of open-source frameworks (PyTorch, TensorFlow, Triton, NeMo) with security patches and long-term support, NIM microservices for production inference, support for VMware vSphere and Red Hat OpenShift virtualization, enterprise support with SLA guarantees, and security certifications (SOC2, HIPAA ready). AI Enterprise is required for production deployment of TensorRT-LLM and other enterprise features in regulated environments. Pricing is per-GPU subscription. The platform enables enterprises to deploy AI anywhere — on-premises data centers, cloud, or edge. AI Enterprise also includes the NVIDIA AI LaunchPad for hybrid cloud deployments and NVIDIA Cloud Physics for simulation workloads. For startups entering enterprise markets, AI Enterprise certification facilitates procurement and compliance processes.""",
    url="https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
    tags=["enterprise", "production", "support", "security", "compliance", "SOC2", "HIPAA"],
)

# === CUDA ===
_add(
    tech="CUDA",
    category="Foundation",
    title="CUDA — Parallel Computing Platform",
    content="""CUDA (Compute Unified Device Architecture) is NVIDIA's parallel computing platform and programming model that enables dramatic increases in computing performance by harnessing the power of NVIDIA GPUs. CUDA provides the foundation for all NVIDIA AI and HPC software, from deep learning frameworks to scientific simulations. Key concepts: CUDA kernels — functions executed in parallel across thousands of GPU threads; thread hierarchy — threads organized in blocks (up to 1024 threads) and grids; memory hierarchy — global memory (high capacity, high latency), shared memory (on-chip, fast), registers (per-thread, fastest); warp scheduling — groups of 32 threads execute in lockstep; compute capability — GPU architecture version (e.g., Ampere=8.0, Hopper=9.0). For AI applications, CUDA enables: massive parallel matrix multiplications for neural network forward/backward passes; custom CUDA kernels for novel operations not covered by cuBLAS/cuDNN; integration with PyTorch via torch.cuda, with TensorFlow via tf.config.list_physical_devices. Startups building AI-native products benefit from: custom CUDA kernels for domain-specific optimizations; understanding compute capability to select right GPU generation; CUDA libraries (cuBLAS, cuDNN, cuFFT, cuSOLVER) for drop-in acceleration without writing kernel code.""",
    url="https://developer.nvidia.com/cuda-toolkit",
    tags=["CUDA", "parallel computing", "GPU", "threads", "memory", "compute capability", "kernels"],
)

_add(
    tech="CUDA",
    category="Libraries",
    title="CUDA-X Libraries — Drop-in GPU Acceleration",
    content="""CUDA-X is a collection of libraries, tools, and technologies that provide GPU-accelerated computing across a wide range of domains. These libraries are drop-in replacements or additions to existing CPU-based code, requiring minimal code changes. Core libraries: cuBLAS — GPU-accelerated basic linear algebra subroutines (matrix multiplication, LU/Cholesky decomposition, solving linear systems); cuDNN — GPU-accelerated primitives for deep learning (convolutions, pooling, normalization, activation functions); cuFFT — fast Fourier transform on GPU; cuSOLVER — dense and sparse direct linear solvers; cuSPARSE — sparse matrix operations; NPP — NVIDIA Performance Primitives for image/video processing; nvJPEG — GPU-accelerated JPEG decoding/encoding. RAPIDS libraries build on CUDA-X: cuDF (GPU DataFrames), cuML (GPU ML algorithms), cuGraph (GPU graph analytics). For startups: using CUDA-X libraries in Python requires minimal changes — replacing numpy operations with cupy equivalents, or using RAPIDS APIs that mirror pandas/sklearn. cuDNN is automatically used by PyTorch and TensorFlow when a CUDA-compatible GPU is available. NVIDIA Nsight Systems provides profiling tools to identify which operations benefit most from GPU acceleration.""",
    url="https://developer.nvidia.com/cuda-toolkit",
    tags=["cuBLAS", "cuDNN", "cuFFT", "libraries", "acceleration", "Nsight", "cuSOLVER", "cuSPARSE"],
)

# === AI Services ===
_add(
    tech="AI Services",
    category="AI-as-a-Service",
    title="NVIDIA AI Services for Enterprise",
    content="""NVIDIA provides pre-trained AI services for common enterprise use cases: Neural Modules for computer vision (people counting, pose detection, anomaly detection), ASR and TTS via Riva services, NIM microservices for LLM inference, NeMo customization services for fine-tuning on proprietary data, and NVIDIA BioNeMo for drug discovery. These services can be accessed via cloud APIs (AWS, Azure, Google Cloud) or deployed on-premises. For startups building on top of NVIDIA technology, these services provide production-ready building blocks that reduce time-to-market. The NVIDIA AI Foundation model ecosystem includes models for vision, language, speech, biology, and robotics. NVIDIA AI Foundation also includes the CUDA-X libraries for specialized acceleration in areas like cryptography, communications, and physics simulation.""",
    url="https://blogs.nvidia.com/blog/ai-5-layer-cake/",
    tags=["foundation models", "cloud", "pre-trained", "BioNeMo", "NeMo", "Riva"],
)

# === AI-Native Services ===
_add(
    tech="AI-Native Services",
    category="Strategy",
    title="AI-Native Services — The New Software Category",
    content="""AI-native services represent a new category of software-as-a-service where the core value delivery is an AI-augmented workflow rather than traditional software automation. Unlike SaaS wrappers of LLMs, AI-native services: own proprietary data that improves the AI model over time, integrate AI deeply into the workflow rather than as a feature, deliver outcomes rather than tools, and use agents that can take actions across systems. Key characteristics: the AI model is not an add-on but the core of the product, the business model aligns with value delivered (outcome-based pricing), data moats are created through usage, and continuous improvement through production feedback loops. NVIDIA's position: providing the infrastructure layer (GPUs, inference optimization, training frameworks) that enables AI-native services to scale efficiently. The 5-layer AI stack: 1) Data (proprietary), 2) Model (foundation models + fine-tuning), 3) Orchestration (agents, RAG), 4) Application (product UX), 5) Distribution (GTM, integrations). NVIDIA covers layers 1-3 with CUDA, RAPIDS, NeMo, Triton, and NIM.""",
    url="https://sequoiacap.com/article/services-the-new-software/",
    tags=["AI-native", "SaaS", "business model", "data moat", "agents", "strategy"],
)

# === Generative AI / Image & Video ===
_add(
    tech="NVIDIA NIM",
    category="Generative AI",
    title="NIM for Generative AI — Image, Video, Audio",
    content="""NVIDIA NIM microservices power generative AI applications across image, video, and audio modalities. For image generation, NIM provides optimized inference for Stable Diffusion XL, FLUX, and SDXL-Turbo models with sub-second latency. For video generation, NIM supports Sora, Gen-3, and Stable Video Diffusion models with TensorRT-LLM acceleration. For audio generation, NIM accelerates MusicGen and AudioLDM. For image editing, NIM supports Instruct-Pix2Pix, ControlNet, and IP-Adapter. NIM is used by startups building: marketing content generation (ads, social media, product imagery), e-commerce (product visualization, virtual try-on), entertainment (video effects, animation), and synthetic data generation for training other models. Each NIM exposes an OpenAI-compatible API, making it trivial to migrate from hosted APIs. For startups currently using OpenAI DALL-E or Stability AI, switching to NIM provides: 5-10x cost reduction, data privacy (models run on owned infrastructure), and no rate limits. NIM runs on any NVIDIA GPU from RTX 4090 to H100.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
    tags=["generative", "image generation", "video generation", "Stable Diffusion", "FLUX", "synthetic data", "marketing", "e-commerce"],
)

_add(
    tech="NVIDIA Omniverse",
    category="Generative AI",
    title="Omniverse for Generative Media",
    content="""NVIDIA Omniverse enables generative AI for 3D content and video. Omniverse integrates with Stable Diffusion through USD-based workflows, allowing text-to-3D and image-to-3D generation. Key use cases: marketing video generation with photorealistic 3D scenes, virtual production for film and advertising, real-time virtual try-on for e-commerce, product configurators for retail, and synthetic training data for computer vision models. Omniverse + Picasso (NVIDIA's foundation model service) provides generative capabilities for 3D assets. For startups building video generation tools, Omniverse provides: real-time path tracing for photorealistic output, USD-based scene composition for collaborative workflows, and integration with diffusion models for content generation. The combination of Omniverse (rendering) + NIM (model serving) + CUDA (acceleration) provides a complete stack for generative media startups.""",
    url="https://www.nvidia.com/en-us/omniverse/",
    tags=["generative", "video", "3D", "rendering", "USD", "virtual production", "synthetic data", "marketing"],
)

# === Expansion: Brasil-specific tech coverage ===

# --- NIM Expansion ---
_add(
    tech="NVIDIA NIM",
    category="NIM Use Cases",
    title="NIM for Brazilian Fintech — Anti-Fraud and Credit Scoring",
    content="""Brazilian fintech startups benefit significantly from NVIDIA NIM for production AI. NIM provides: optimized inference for fraud detection models (10-50x faster than CPU), low-latency credit scoring APIs (sub-50ms responses), multilingual support for Portuguese, Spanish, and English, and OpenAI-compatible API for easy integration with existing systems. Use cases in Brazilian fintech: real-time fraud detection on PIX transactions, credit scoring with explainable AI for BACEN compliance, anti-money laundering (AML) using Morpheus, customer service chatbots for bancários, and document intelligence for KYC. NIM runs on NVIDIA L40S, A100, and H100 GPUs available through AWS, Azure, Google Cloud, and OCI. For startups in the NVIDIA Inception program, additional GPU credits are available to offset cloud costs. NIM integrates with LangChain and LlamaIndex for RAG applications, with Triton for high-throughput serving, and with NeMo Guardrails for safe AI responses.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/",
    tags=["fintech", "fraud", "credit", "PIX", "BACEN", "Brazil", "compliance", "Portuguese"],
)

_add(
    tech="NVIDIA NIM",
    category="NIM Use Cases",
    title="NIM for Healthcare — Brazilian Hospitals and Diagnostics",
    content="""NVIDIA NIM powers healthcare AI applications in Brazilian hospitals and diagnostic clinics. For medical imaging: NIM accelerates CT, MRI, and X-ray analysis with Clara + MONAI integration. For clinical text: NIM serves LLMs fine-tuned for medical Portuguese (BERTimbau, Sabiá). For drug discovery: NIM integrates with BioNeMo for molecular generation. Use cases: Dasa (Brazil) uses GPU-accelerated AI for diagnostic imaging at scale, Hospital Albert Einstein deploys LLM-powered clinical assistants, Fleury uses AI for lab result interpretation. NIM in healthcare: HIPAA and LGPD compliance through on-premises deployment, integration with PACS and HIS systems via DICOM, support for Brazilian Portuguese medical terminology, and explainable AI for clinical decision support. The Clara + NIM combination provides: medical imaging models (chest X-ray, mammography, dermatology), clinical NLP models, and genomic analysis pipelines.""",
    url="https://www.nvidia.com/en-us/clara/",
    tags=["healthcare", "diagnostics", "medical imaging", "DICOM", "LGPD", "Brazil", "Clara", "MONAI", "Dasa", "Einstein"],
)

# --- Clara Expansion ---
_add(
    tech="NVIDIA Clara",
    category="Healthcare AI",
    title="Clara for Medical Imaging at Scale",
    content="""NVIDIA Clara is the healthcare AI platform for medical imaging, genomics, and clinical workflows. Clara provides: pre-trained models for chest X-ray (CheXNet), CT segmentation (nnU-Net), mammography, dermatology, and pathology; the MONAI framework for medical imaging deep learning; integration with DICOM, HL7, and FHIR standards; and deployment on NVIDIA RTX, A100, and H100 GPUs. Clara is used by Brazilian startups like Dasa for diagnostic imaging acceleration, Alice for clinical decision support, and Pixeon for PACS-AI integration. Key capabilities: federated learning for multi-hospital training without sharing patient data, synthetic data generation for rare conditions, automated quality control of medical images, and quantitative imaging biomarkers. Clara's Clara Guardian enables patient monitoring with sensor fusion. The platform supports Brazilian Portuguese medical terminology and integrates with SUS (Sistema Único de Saúde) workflows.""",
    url="https://www.nvidia.com/en-us/clara/",
    tags=["medical imaging", "diagnostics", "DICOM", "MONAI", "PACS", "federated learning", "SUS", "Brazilian Portuguese"],
)

_add(
    tech="MONAI",
    category="Medical Imaging",
    title="MONAI Framework for Medical AI",
    content="""MONAI (Medical Open Network for AI) is a PyTorch-based framework for healthcare imaging. It provides domain-specific transforms, network architectures, and evaluation metrics for medical imaging tasks. Key components: MONAI Core (training and inference), MONAI Label (annotation tools with active learning), MONAI Deploy (clinical deployment), and MONAI Bundle (pre-trained model zoo). Brazilian use cases: tumor segmentation in CT/MRI, organ segmentation for surgical planning, lesion detection in mammography, COVID-19 pneumonia detection, and cardiac MRI analysis. MONAI is integrated with Clara, NIM, and Triton for production deployment. The framework supports federated learning for multi-institution training without data sharing — critical for Brazilian hospital networks. MONAI Label enables radiologists to annotate efficiently with AI-assisted labeling, reducing annotation time by 5-10x.""",
    url="https://monai.io/",
    tags=["MONAI", "PyTorch", "medical imaging", "segmentation", "annotation", "federated learning"],
)

# --- RAPIDS Expansion ---
_add(
    tech="RAPIDS",
    category="Data Science",
    title="RAPIDS for Brazilian Finance and Retail",
    content="""NVIDIA RAPIDS accelerates data science and ML workflows on NVIDIA GPUs. The library includes cuDF (pandas-compatible DataFrames), cuML (scikit-learn-compatible ML), cuGraph (network analysis), and cuSpatial (geospatial). For Brazilian finance: RAPIDS accelerates credit scoring on 100M+ customer datasets, fraud detection pipelines, and risk modeling. Use cases: Stone processes transaction data 10x faster, PicPay accelerates churn prediction, iFood optimizes logistics with cuGraph, and Nubank trains credit models on full historical data. For retail: RAPIDS powers recommendation engines (cuML), demand forecasting, and customer segmentation. Performance gains: typical 10-50x speedup over CPU pandas/sklearn. RAPIDS integrates with PySpark via Spark RAPIDS plugin, with Dask for distributed computing, and with MLflow for experiment tracking. The library is fully open source and drops into existing pandas/sklearn code with minimal changes.""",
    url="https://rapids.ai/",
    tags=["RAPIDS", "cuDF", "cuML", "cuGraph", "data science", "fintech", "retail", "Brazil", "performance"],
)

_add(
    tech="cuDF",
    category="Data Science",
    title="cuDF — GPU DataFrames for ETL",
    content="""cuDF is a GPU-accelerated DataFrame library compatible with pandas API. It provides 10-100x faster data processing for ETL, feature engineering, and data preparation pipelines. Brazilian use cases: Nubank processes 100M+ transactions in minutes instead of hours, iFood analyzes 50M+ delivery events for real-time pricing, Stone builds fraud detection features 50x faster, and Loggi optimizes routes with cuSpatial. cuDF supports: pandas-compatible API for easy migration, Apache Arrow for zero-copy data exchange, Dask cuDF for distributed processing, Polars backend for query optimization, and integration with Spark via Spark RAPIDS. Key performance tips: keep data on GPU throughout the pipeline, use cudf.pandas for automatic GPU acceleration, and leverage Dask for datasets larger than GPU memory.""",
    url="https://docs.rapids.ai/api/cudf/stable/",
    tags=["cuDF", "pandas", "ETL", "DataFrame", "Arrow", "Spark", "Dask", "performance"],
)

# --- Isaac Expansion ---
_add(
    tech="NVIDIA Isaac",
    category="Robotics",
    title="Isaac for Robotics Startups",
    content="""NVIDIA Isaac is the robotics platform for developing, simulating, and deploying autonomous robots. Components: Isaac Sim (photorealistic simulation), Isaac Lab (robot learning), Isaac ROS (production ROS 2 packages), and Jetson (edge AI compute). Brazilian use cases: agricultural drones for precision agriculture (using Isaac for path planning), warehouse robotics for fulfillment centers, autonomous vehicles for last-mile delivery, and industrial inspection robots. Isaac Sim provides: photorealistic simulation with ray-traced rendering, synthetic data generation for training perception models, digital twin capabilities for factory automation, and integration with ROS 2. Jetson Orin Nano and AGX provide edge AI for robots with up to 275 TOPS. The platform enables startups to: train robots in simulation before deployment, generate synthetic data for rare scenarios, deploy on edge devices, and integrate with existing ROS 2 stacks. Isaac is particularly valuable for Brazilian agtech and logistics startups.""",
    url="https://developer.nvidia.com/isaac",
    tags=["Isaac", "robotics", "simulation", "Jetson", "ROS 2", "agtech", "logistics", "synthetic data"],
)

# --- Morpheus Expansion ---
_add(
    tech="NVIDIA Morpheus",
    category="Cybersecurity",
    title="Morpheus for Brazilian Cybersecurity",
    content="""NVIDIA Morpheus is a cybersecurity AI framework for detecting threats in real-time. It uses GPU-accelerated inference to analyze network traffic, logs, and user behavior at scale. Brazilian use cases: real-time fraud detection on PIX transactions, anti-money laundering (AML) compliance for financial institutions, threat detection in corporate networks, and security monitoring for cloud workloads. Morpheus capabilities: digital fingerprinting for user behavior analysis, sensitive data detection (LGPD compliance), phishing detection in emails, malware classification, and anomaly detection in network flows. Performance: 100x faster than CPU-based threat detection, enabling real-time analysis of billions of events per day. Integration: SIEM systems (Splunk, QRadar), data lakes (S3, MinIO), and security orchestration platforms. For startups in the Inception program, Morpheus reference architectures and example notebooks are available.""",
    url="https://developer.nvidia.com/morpheus",
    tags=["Morpheus", "cybersecurity", "fraud detection", "PIX", "AML", "LGPD", "SIEM", "real-time"],
)

# --- NeMo Expansion ---
_add(
    tech="NVIDIA NeMo",
    category="LLM Framework",
    title="NeMo for LLM Fine-Tuning in Portuguese",
    content="""NVIDIA NeMo is an end-to-end framework for developing generative AI models including LLMs, speech, and multimodal. For Brazilian startups, NeMo enables: fine-tuning foundation models (Llama, Mistral) on Brazilian Portuguese data, continued pre-training on domain-specific corpora (legal, medical, financial), RLHF and DPO for alignment, and deployment via NIM microservices. Key techniques: LoRA and QLoRA for parameter-efficient fine-tuning, knowledge distillation for smaller models, PEFT (parameter-efficient fine-tuning), and model parallelism for large models. Brazilian use cases: fine-tuning models on Brazilian Portuguese legal documents (BERTimbau base), training medical LLMs on Brazilian clinical notes, creating financial advisors fine-tuned on Brazilian banking regulations, and speech models for Brazilian Portuguese (Riva integration). NeMo Curator provides data curation tools for filtering and deduplication. NeMo Guardrails adds safety layers to LLM applications. The framework is fully open source and runs on multi-GPU setups including A100, H100, and B200.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/nemo/",
    tags=["NeMo", "LLM", "fine-tuning", "LoRA", "RLHF", "Portuguese", "Brazilian", "BERTimbau"],
)

_add(
    tech="NeMo Guardrails",
    category="AI Safety",
    title="NeMo Guardrails for Production AI Safety",
    content="""NeMo Guardrails adds programmable safety layers to LLM applications, enabling startups to deploy AI agents safely in production. Capabilities: dialog management (topical rails), input/output safety (jailbreak detection, PII filtering), fact-checking against knowledge bases, action validation (preventing unauthorized tool calls), and integration with NIM microservices. Brazilian use cases: preventing LLMs from giving incorrect financial advice, ensuring medical AI applications follow clinical guidelines, blocking PII leakage for LGPD compliance, and validating AI agent actions in enterprise systems. Implementation: Colang programming language for defining rails, integration with LangChain and LlamaIndex, and support for OpenAI, Anthropic, and self-hosted models. For startups, NeMo Guardrails reduces the risk of deploying LLMs in customer-facing applications and helps meet regulatory requirements.""",
    url="https://github.com/NVIDIA/NeMo-Guardrails",
    tags=["NeMo Guardrails", "AI safety", "LGPD", "compliance", "PII", "jailbreak", "production"],
)

# --- Riva Expansion ---
_add(
    tech="NVIDIA Riva",
    category="Speech AI",
    title="Riva for Brazilian Portuguese Speech AI",
    content="""NVIDIA Riva is a GPU-accelerated speech AI SDK for ASR (automatic speech recognition), TTS (text-to-speech), and NMT (neural machine translation). Brazilian Portuguese support: state-of-the-art ASR for Brazilian Portuguese with sub-300ms latency, TTS voices for Brazilian Portuguese (male and female), and code-switching support for Portuguese-English mixed speech. Use cases: contact center transcription and analytics, voice bots for customer service, accessibility tools (real-time captioning), and voice interfaces for IoT devices. Performance: 10-100x faster than CPU-based speech processing, enabling real-time transcription of thousands of concurrent calls. Integration: telephony systems (Twilio, Genesys), contact center platforms, mobile SDKs for iOS/Android, and web SDKs. Riva models can be fine-tuned on domain-specific vocabulary (medical, legal, financial) for improved accuracy. The SDK is available as containers for cloud or on-premises deployment.""",
    url="https://www.nvidia.com/en-us/ai-data-science/products/riva/",
    tags=["Riva", "ASR", "TTS", "speech", "Portuguese", "Brazilian", "contact center", "voice bot"],
)

# --- Triton Expansion ---
_add(
    tech="Triton",
    category="MLOps",
    title="Triton Inference Server for Production ML",
    content="""NVIDIA Triton Inference Server is an open-source serving platform for ML models in production. It supports: multiple frameworks (PyTorch, TensorFlow, ONNX, TensorRT, Python), dynamic batching for GPU efficiency, concurrent model execution, model versioning and A/B testing, and metrics export to Prometheus. Brazilian use cases: serving recommendation models for e-commerce, deploying fraud detection at scale, hosting LLMs with NIM integration, and multi-model pipelines for computer vision. Performance features: dynamic batching (up to 10x throughput improvement), model analyzer for optimal GPU configuration, ensemble models for multi-stage inference, and BLS (Business Logic Scripting) for custom logic. Integration: Kubernetes via Helm charts, cloud platforms (AWS SageMaker, Azure ML, Vertex AI), monitoring (Prometheus, Grafana), and CI/CD pipelines. Triton is the recommended serving platform for NIM microservices and is used by Brazilian unicorns for production AI.""",
    url="https://github.com/triton-inference-server/server",
    tags=["Triton", "inference", "MLOps", "production", "Kubernetes", "batching", "monitoring"],
)

# --- TensorRT-LLM Expansion ---
_add(
    tech="TensorRT-LLM",
    category="LLM Optimization",
    title="TensorRT-LLM for Brazilian LLM Deployment",
    content="""TensorRT-LLM is a library for optimizing LLM inference on NVIDIA GPUs. It provides: kernel optimizations for transformer architectures, in-flight batching for higher throughput, paged attention for memory efficiency, quantization (INT8, FP8, INT4), and multi-GPU inference (tensor and pipeline parallelism). Performance gains: 2-8x throughput improvement over PyTorch, 50-70% latency reduction, and up to 90% memory reduction with quantization. Brazilian use cases: deploying Llama 3 fine-tuned for Brazilian Portuguese, hosting BERTimbau with lower latency, optimizing Sabiá models for production, and serving code generation models for Brazilian developers. Integration: NIM (pre-optimized containers), Triton Inference Server, and direct C++/Python APIs. TensorRT-LLM Engine Builder optimizes models for specific GPU targets (A100, H100, L40S). For startups with high-volume LLM serving needs, TensorRT-LLM can dramatically reduce cloud costs.""",
    url="https://github.com/NVIDIA/TensorRT-LLM",
    tags=["TensorRT-LLM", "LLM", "optimization", "inference", "quantization", "Portuguese", "production"],
)

# --- AI Enterprise Expansion ---
_add(
    tech="AI Enterprise",
    category="Enterprise AI",
    title="AI Enterprise for Brazilian Compliance",
    content="""NVIDIA AI Enterprise is a software platform that provides enterprise-grade AI software, frameworks, and tools with security, stability, and support. Components: NIM microservices (production-ready), NeMo framework, Triton Inference Server, Clara, RAPIDS, and enterprise support (SLAs, security patches, prior notifications). For Brazilian enterprises and startups serving enterprise customers, AI Enterprise provides: SOC 2 Type II compliance (important for selling to US enterprises), LGPD compliance features, vulnerability management and security patches, single point of contact for support, and certified configurations for production. Pricing: per-GPU annual subscription, available through NVIDIA Cloud Partners (AWS, Azure, GCP, OCI). For startups in NVIDIA Inception, AI Enterprise licenses are available at significant discounts. AI Enterprise differentiates from open source: production hardening, security certifications, enterprise support, and guaranteed SLAs.""",
    url="https://www.nvidia.com/en-us/data-center/products/ai-enterprise/",
    tags=["AI Enterprise", "compliance", "LGPD", "SOC 2", "enterprise", "support", "SLA"],
)

# --- cuML Expansion ---
_add(
    tech="cuML",
    category="Data Science",
    title="cuML for Brazilian Machine Learning",
    content="""NVIDIA cuML is a GPU-accelerated ML library compatible with scikit-learn API. Algorithms: classification (LogisticRegression, SVM, RandomForest, XGBoost), regression (LinearRegression, Ridge, Lasso, KNN), clustering (KMeans, DBSCAN, HDBSCAN), dimensionality reduction (PCA, t-SNE, UMAP), and time series (ARIMA, Prophet, Holt-Winters). Brazilian use cases: customer segmentation for retail (KMeans on millions of customers), fraud detection with XGBoost (Stone, Nubank), credit scoring with ensemble methods, recommendation with matrix factorization, and NLP with TF-IDF + SVM. Performance: 10-100x faster than scikit-learn on GPUs, enabling training on larger datasets in shorter time. Integration: scikit-learn-compatible API for easy migration, Dask cuML for distributed computing, and cuML benchmarks for performance optimization. cuML also provides UMAP and t-SNE for high-dimensional data visualization, crucial for understanding customer behavior patterns.""",
    url="https://docs.rapids.ai/api/cuml/stable/",
    tags=["cuML", "XGBoost", "scikit-learn", "ML", "clustering", "fintech", "retail", "Brazil"],
)

# --- CUDA Expansion ---
_add(
    tech="CUDA",
    category="GPU Computing",
    title="CUDA for High-Performance AI",
    content="""NVIDIA CUDA is the parallel computing platform and programming model for NVIDIA GPUs. It provides: C/C++ extensions for GPU programming, libraries (cuBLAS, cuFFT, cuDNN, cuSPARSE), profiler (Nsight) for performance optimization, and support for multi-GPU and multi-node systems. For startups building proprietary AI: CUDA enables custom kernels for unique operations (e.g., novel attention mechanisms, custom quantization), integration with PyTorch via custom CUDA extensions, high-performance training on large models, and low-latency inference for time-critical applications. Brazilian use cases: training large LLMs in Portuguese (multi-GPU), developing custom CNN architectures for medical imaging, real-time video processing for security, and high-frequency trading models. CUDA requires C/C++ expertise but provides the highest performance for custom AI workloads.""",
    url="https://developer.nvidia.com/cuda-toolkit",
    tags=["CUDA", "GPU programming", "parallel", "C++", "PyTorch", "custom kernels", "performance"],
)

# --- Inception Expansion ---
_add(
    tech="NVIDIA Inception",
    category="Brazil Program",
    title="NVIDIA Inception Brasil — Latin America Focus",
    content="""NVIDIA Inception has a strong focus on the Latin American market, with dedicated resources for Brazilian startups. The Inception Brasil program provides: dedicated NVIDIA team for LATAM, local events and meetups (SP, RJ, tech conferences), connections to Brazilian enterprise customers, and partnerships with local VCs and accelerators. Brazilian members get access to: GPU credits through AWS, Azure, GCP, and OCI partnerships, technical workshops in Portuguese, mentorship from NVIDIA solution architects, and introductions to NVIDIA's global investor network. Active Inception members in Brazil include: startups across fintech, healthcare, agtech, logistics, retail, and enterprise AI. The program hosts: NVIDIA Fintech Day LATAM (annual), Healthcare AI Forum, AgTech Innovation Summit, and Demo Days for portfolio companies. Application is free and available to startups at all stages. Members gain visibility through NVIDIA marketing channels and at GTC (GPU Technology Conference).""",
    url="https://www.nvidia.com/en-us/startups/",
    tags=["Inception", "Brazil", "LATAM", "Brasil", "Portuguese", "local", "community", "events"],
)

# --- Domain-specific Brazilian ---
_add(
    tech="NVIDIA NIM",
    category="AgTech",
    title="NIM and RAPIDS for Brazilian Agriculture",
    content="""Brazilian agtech startups use NVIDIA technology to power precision agriculture solutions. NIM and RAPIDS enable: yield prediction models on satellite imagery (Planet, Sentinel-2), crop disease detection with computer vision, soil analysis with multi-spectral data, weather forecasting with GPU-accelerated models, and farm management optimization. Brazilian agtech examples: Solinftec uses AI for farm operations optimization, Aegro provides farm management with yield predictions, Nagro offers credit scoring for farmers, and Sensix uses drone imagery for precision agriculture. NVIDIA technology stack: RAPIDS for processing satellite and sensor data, NIM for serving ML models, Clara/MONAI for image analysis (crop diseases), Omniverse for digital twins of farms, and Jetson for edge deployment in tractors and drones. The agtech sector is a strategic focus for NVIDIA Inception Brasil.""",
    url="https://www.nvidia.com/en-us/industries/agriculture/",
    tags=["agtech", "agriculture", "satellite", "precision", "drone", "yield", "Brazil", "Solinftec", "Aegro"],
)

_add(
    tech="NVIDIA NIM",
    category="Logistics",
    title="NIM and cuDF for Brazilian Logistics",
    content="""Brazilian logistics startups use NVIDIA technology to optimize deliveries, fleet management, and supply chain operations. Key applications: route optimization with real-time traffic (Loggi, SuperFrete), delivery time prediction (ETA models), dynamic pricing for freight, warehouse robotics with Isaac, and last-mile delivery optimization. Performance gains: cuDF processes 10-100x faster for large logistics datasets, NIM serves optimization models with low latency, Isaac simulates warehouse robots before deployment, and Triton handles high-throughput predictions. Brazilian logistics challenges: vast geography (continental scale), complex urban traffic (São Paulo, Rio), seasonal variations (weather, holidays), and cross-border operations (Mercosul). NVIDIA technology helps startups address these challenges with: real-time data processing, scalable ML serving, simulation for planning, and edge AI for delivery vehicles.""",
    url="https://www.nvidia.com/en-us/industries/retail/",
    tags=["logistics", "loggi", "delivery", "routing", "optimization", "fleet", "Brazil", "last-mile"],
)


_ensure_kb()


def export_jsonl(path: Path | None = None, force_synthetic: bool = False) -> Path:
    """Serializa a KB atual (ou a sintética) para uma linha JSONL por conceito.

    Permite versionar/editar a base de conhecimento fora do código. Se
    `force_synthetic=True`, a KB é reconstruída a partir do conteúdo embutido
    (útil para regenerar o arquivo a partir das entradas `_add` do módulo).
    """
    out_path = Path(path) if path is not None else _JSONL_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if force_synthetic:
        _reload_synthetic_only()

    with open(out_path, "w", encoding="utf-8") as f:
        for c in NVIDIA_KB:
            f.write(
                json.dumps(
                    {
                        "id": c.id,
                        "tech": c.tech,
                        "category": c.category,
                        "title": c.title,
                        "content": c.content,
                        "url": c.url,
                        "tags": c.tags,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    logger.info(f"Exported {len(NVIDIA_KB)} concepts → {out_path}")
    return out_path


def _reload_synthetic_only() -> None:
    """Recarrega apenas as entradas sintéticas do módulo, ignorando JSONL/real.

    Usado por export_jsonl(force_synthetic=True): recarrega o módulo em um
    namespace limpo. Com _ensure_kb() _KB_LOADED=False é reinicializado e a
    carga segue a ordem real > JSONL > sintético.
    """
    import importlib
    import sys

    module = sys.modules[__name__]
    return importlib.reload(module)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NVIDIA KB CLI")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Serializa a KB atual para rag/ingest/data/nvidia_concepts.jsonl",
    )
    parser.add_argument(
        "--export-synthetic",
        action="store_true",
        help="Regenera o JSONL a partir das entradas embutidas no módulo",
    )
    parser.add_argument("--output", type=Path, default=None, help="Caminho de saída (opcional)")
    args = parser.parse_args()

    if args.export:
        export_jsonl(args.output)
    elif args.export_synthetic:
        export_jsonl(args.output, force_synthetic=True)
    else:
        parser.error("informe --export ou --export-synthetic")
