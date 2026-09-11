"""Shared state for the LangGraph multi-agent pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QueryResult:
    """Saída do nó query_planner: consulta estruturada em keywords e filtros."""
    raw_query: str
    keywords: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)
    strategy: str = ""


@dataclass
class ExtractedProfile:
    """Perfil estruturado de uma startup extraído pelo nó extractor."""
    nome: str
    site: str
    descricao: str
    stack: list[str]
    casos_uso: list[str]
    gaps_identificados: list[str]
    sinais_ai: list[str]
    # Novos campos TAPI anti-wrapper
    proprietary_data: list[str] = field(default_factory=list)
    workflow_depth: list[str] = field(default_factory=list)
    custom_model: list[str] = field(default_factory=list)
    distribution: list[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """Resultado do nó classifier: maturidade AI-native, moat e fit Inception."""
    # Categoria: ai_native | ai_enabled | non_ai
    categoria: str  # "ai_native" | "ai_enabled" | "non_ai"
    confianca: float
    justificativa: str
    evidencia_ai: list[str]
    # Scores de defensibilidade
    moat_score: float = 0.0  # 0-5 escala
    wrapper_warning: bool = False
    inception_fit_score: float = 0.0  # 0-1
    fit_breakdown: dict = field(default_factory=dict)  # moat/tech/sector/traction


@dataclass
class EvidenceResult:
    """Validação de evidências (documentos) de uma startup (nó evidence_validator)."""
    valido: bool
    evidencias: list[dict]
    lacunas: list[str]
    confianca: float


@dataclass
class NVIDIAReference:
    """Referência RAG recuperada e validada (groundedness) para uma startup."""
    tech: str
    title: str
    content: str
    url: str
    score: float
    relevance_to_gap: str


@dataclass
class Recommendation:
    """Recomendação NVIDIA emitida pelo Recommendation Agent (com fontes RAG)."""
    tecnologia: str
    justificativa_tecnica: str
    justificativa_negocio: str
    prioridade: str  # high | medium | low
    complexidade: str  # low | medium | high
    proxima_acao: str
    evidencias: list[str]
    fontes_rag: list[dict] = field(default_factory=list)


@dataclass
class Briefing:
    """Briefing executivo final (3 ângulos) gerado pelo nó briefing."""
    empresa: str
    setor: str
    maturidade_ai: str
    score_maturidade: float
    recomendacoes: list[Recommendation]
    # Próximos passos em 3 dimensões (TAPI §2.6)
    proximos_comerciais: list[str] = field(default_factory=list)
    proximos_tecnicos: list[str] = field(default_factory=list)
    proximos_comunitarios: list[str] = field(default_factory=list)
    # Fit e warning
    inception_fit_score: float = 0.0
    wrapper_warning: bool = False
    fit_breakdown: dict = field(default_factory=dict)
    # Critério que selecionou esta startup (relevance × fit) — transparência anti-"aleatório"
    criterio_selecao: str = ""
    # Nutrição
    nurture_suggestion: str = ""
    # Fontes
    fontes_consultadas: list[str] = field(default_factory=list)
    fontes_rag: list[dict] = field(default_factory=list)
    generated_at: str = ""
    # Set True by graph when >50% startups have valido=False
    evidencia_insuficiente: bool = False


@dataclass
class Telemetry:
    """Runtime instrumentation for each pipeline run (decision data).

    Collected by per-node wrappers in agents/graph.py and the retriever,
    then persisted to logs/telemetry-*.ndjson by agents/observability.py.
    """
    run_id: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    node_timings: dict = field(default_factory=dict)      # node -> total ms
    node_counts: dict = field(default_factory=dict)       # node -> # calls
    node_token_usage: dict = field(default_factory=dict)  # node -> {model, prompt_tokens, completion_tokens, latency_ms}
    retrieval_scores_pre_rerank: dict = field(default_factory=dict)   # rag_query -> list[float]
    retrieval_scores_post_rerank: dict = field(default_factory=dict)  # rag_query -> list[float]
    rerank_effectiveness: dict = field(default_factory=dict)          # rag_query -> {reorder_fraction, kendall_tau, n_pool}
    evidence_reasons: dict = field(default_factory=dict)  # startup nome -> reason
    low_evidence: bool = False


@dataclass
class AgentState:
    """Estado compartilhado do grafo LangGraph (canais de leitura/escrita)."""
    user_query: str = ""
    query_result: QueryResult | None = None
    retrieved_startups: list[dict] = field(default_factory=list)
    retrieval_strategy: str = ""
    extracted_profiles: list[dict] = field(default_factory=list)
    classifications: list[dict] = field(default_factory=list)
    evidence_results: list[dict] = field(default_factory=list)
    nvidia_references: list[dict] = field(default_factory=list)
    recommendations: list[dict] = field(default_factory=list)
    briefing: Briefing | None = None
    errors: list[str] = field(default_factory=list)
    next_agent: str = ""
    selected_startup: dict | None = None
    # Set by supervisor when >50% inválidos (sinal preservado do fluxo antigo).
    # Honored by nvidia_rag to skip Cohere/Qdrant calls.
    low_evidence: bool = False
    # Controle do supervisor (atópico):
    #   replan_count  — nº de vezes que voltamos ao query_planner
    #   retry_count   — nº de vezes que voltamos ao retriever
    #   retriever_limit — LIMIT SQL usado pelo nó retriever (retry amplia)
    #   rag_top_k     — top_k do RAG externo executado pelo nó nvidia_rag
    #   expand_query  — flag sinalizando replan (query_planner omite filtros)
    #   supervisor_actions — trilha de auditoria das decisões do supervisor
    replan_count: int = 0
    retry_count: int = 0
    retriever_limit: int = 25
    rag_top_k: int = 2
    expand_query: bool = False
    supervisor_actions: list[str] = field(default_factory=list)
    telemetry: Telemetry = field(default_factory=Telemetry)
