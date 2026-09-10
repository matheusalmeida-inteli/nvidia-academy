"use client";

import { useState } from "react";
import {
  Search,
  Sparkles,
  ArrowRight,
  AlertTriangle,
  Compass,
  Activity,
  TrendingUp,
  Cpu,
  Download,
} from "lucide-react";
import {
  submitQuery,
  exportBriefing,
  type QueryResponse,
} from "@/lib/api";
import { BriefingPanel } from "@/components/BriefingPanel";
import { StartupCard } from "@/components/StartupCard";

const SUGGESTIONS = [
  {
    label: "AI-native em fintech",
    query: "Startups AI-native de fintech com dados próprios",
    icon: TrendingUp,
  },
  {
    label: "Saúde com IA médica",
    query: "Startups de saúde com modelos de imagem médica",
    icon: Activity,
  },
  {
    label: "Logística com gap GPU",
    query: "AI-native startups no setor de logística com gap GPU",
    icon: Cpu,
  },
  {
    label: "Defesa contra wrappers",
    query: "Startups com defensibilidade real (não wrappers de LLM)",
    icon: Sparkles,
  },
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const onExport = async () => {
    if (!query.trim() || loading || exporting) return;
    setExporting(true);
    try {
      await exportBriefing(query, 8);
    } catch (e: any) {
      setError(e.message || "Erro ao exportar briefing");
    } finally {
      setExporting(false);
    }
  };

  const onSubmit = async (q: string) => {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
    setQuery(q);
    try {
      const data = await submitQuery(q, 8);
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Erro ao processar consulta");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-full">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <header className="mb-10">
          <div className="flex items-baseline gap-3 mb-2">
            <h1 className="text-3xl font-semibold tracking-tighter text-text-primary">
              Análise de Startups
            </h1>
            <span className="badge-ai-native">Multi-agente</span>
          </div>
          <p className="text-text-secondary text-sm max-w-2xl leading-relaxed">
            Pipeline LangGraph com 9 agentes (supervisor hub + retry/replan)
            que classifica startups brasileiras, detecta wrappers de LLM,
            avalia defensibilidade e recomenda tecnologias NVIDIA Inception.
            Fontes: 56 startups, 224 documentos, NVIDIA Knowledge Base.
          </p>
        </header>

        {/* Search bar */}
        <section className="mb-8">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onSubmit(query)}
              placeholder="Ex: startups AI-native de fintech com gap em inferência GPU"
              className="w-full bg-bg-surface border border-border-default rounded-md pl-11 pr-32 h-12 text-base text-text-primary placeholder:text-text-tertiary
                         focus:outline-none focus:border-accent-green focus:shadow-[0_0_0_3px_rgba(118,185,0,0.12)]
                         transition-all duration-150"
              disabled={loading}
            />
            <button
              onClick={() => onSubmit(query)}
              disabled={loading || !query.trim()}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 h-9 px-4 inline-flex items-center gap-1.5
                         bg-accent-green text-text-inverse text-sm font-medium rounded
                         hover:bg-accent-green-soft disabled:opacity-40 disabled:cursor-not-allowed
                         transition-colors"
            >
              {loading ? "Analisando..." : "Analisar"}
              {!loading && <ArrowRight size={14} strokeWidth={2.5} />}
            </button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-text-tertiary mr-1">Sugestões</span>
            {SUGGESTIONS.map(({ label, query, icon: Icon }) => (
              <button
                key={label}
                onClick={() => onSubmit(query)}
                disabled={loading}
                className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded text-xs
                           border border-border-subtle text-text-secondary
                           hover:text-text-primary hover:border-border-default hover:bg-bg-surface
                           disabled:opacity-40 transition-colors"
              >
                <Icon size={11} strokeWidth={2.5} />
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* Error */}
        {error && (
          <div className="mb-6 flex items-start gap-3 p-4 rounded-md border border-accent-red/30 bg-accent-red-dim">
            <AlertTriangle size={16} className="text-accent-red shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-accent-red">Erro no pipeline</p>
              <p className="text-xs text-text-secondary mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <div className="skeleton h-6 w-48" />
              <div className="skeleton h-40 w-full" />
              <div className="skeleton h-40 w-full" />
              <div className="skeleton h-40 w-full" />
            </div>
            <div className="skeleton h-96 w-full" />
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && !error && (
          <EmptyState onSuggestion={onSubmit} />
        )}

        {/* Results */}
        {result && !loading && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">
            <div className="lg:col-span-2 space-y-6">
              {/* Stats bar */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary tracking-tight">
                    {result.startups.length} startups analisadas
                  </h2>
                  <p className="text-xs text-text-tertiary mt-0.5">
                    {result.total_found} correspondências no portfólio · Classificadas por TAPI §3
                  </p>
                </div>
                {result.query_keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 max-w-md justify-end">
                    {result.query_keywords.slice(0, 5).map((k) => (
                      <span
                        key={k}
                        className="text-2xs px-1.5 h-5 inline-flex items-center rounded
                                   bg-bg-surface border border-border-subtle text-text-secondary"
                      >
                        {k}
                      </span>
                    ))}
                  </div>
                )}
                <button
                  onClick={onExport}
                  disabled={loading || exporting}
                  className="inline-flex items-center gap-1.5 h-8 px-3 rounded text-xs font-medium
                             border border-border-default text-text-secondary
                             hover:text-text-primary hover:border-accent-green hover:bg-bg-surface
                             disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Download size={13} strokeWidth={2.5} />
                  {exporting ? "Exportando..." : "Exportar briefing"}
                </button>
              </div>

              {/* Startup list */}
              <div className="space-y-3">
                {result.startups.map((s) => (
                  <StartupCard key={s.nome} startup={s} />
                ))}
              </div>
            </div>

            {/* Briefing sidebar */}
            <aside className="lg:col-span-1">
              {result.briefing && <BriefingPanel briefing={result.briefing} />}
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ onSuggestion }: { onSuggestion: (q: string) => void }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <div className="col-span-1 lg:col-span-2 card p-6">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-md bg-accent-green-dim shrink-0">
            <Compass size={18} className="text-accent-green" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary mb-1">
              Como usar
            </h3>
            <p className="text-xs text-text-secondary leading-relaxed max-w-2xl">
              Faça uma consulta em linguagem natural sobre o setor, moat ou
              stack que você está procurando. O pipeline executa 9 agentes —
              Query Planner, Retriever, Extractor, Classifier, Evidence
              Validator, Supervisor (retry/replan), NVIDIA RAG, Recommendation,
              Briefing — e retorna startups ranqueadas por <em>Inception Fit</em>
              com classificação anti-wrapper.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
