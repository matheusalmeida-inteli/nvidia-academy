"use client";

import { useState, useEffect } from "react";
import {
  GitBranch,
  Filter,
  TrendingUp,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Users,
  Target,
  Search,
  Trash2,
  ChevronRight,
} from "lucide-react";
import {
  listCandidates,
  updateCandidate,
  deleteCandidate,
  type Candidate,
} from "@/lib/api";

const STATUS_ORDER = [
  "identificado",
  "contatado",
  "engajado",
  "onboarding",
];

const STATUS_META: Record<string, { label: string; color: string; icon: React.ComponentType<any> }> = {
  identificado: { label: "Identificado", color: "text-text-secondary border-border-default bg-bg-surface", icon: Target },
  contatado: { label: "Contatado", color: "text-accent-blue border-accent-blue/30 bg-accent-blue-dim", icon: Clock },
  engajado: { label: "Engajado", color: "text-accent-green border-accent-green/30 bg-accent-green-dim", icon: TrendingUp },
  onboarding: { label: "Onboarding", color: "text-accent-purple border-accent-purple/30 bg-accent-purple-dim", icon: CheckCircle2 },
};

const CADENCE_DOT: Record<string, string> = {
  semanal: "bg-accent-red",
  quinzenal: "bg-accent-amber",
  mensal: "bg-accent-green",
  inativo: "bg-text-tertiary",
};

export default function PipelinePage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    listCandidates({})
      .then(setCandidates)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = candidates.filter((c) => {
    if (filter !== "all" && c.status !== filter) return false;
    if (search && !c.startup_nome?.toLowerCase().includes(search.toLowerCase()))
      return false;
    return true;
  });

  const handleStatus = async (id: number, status: string) => {
    await updateCandidate(id, { status });
    setCandidates((cs) => cs.map((c) => (c.id === id ? { ...c, status } : c)));
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remover este candidato do pipeline?")) return;
    await deleteCandidate(id);
    setCandidates((cs) => cs.filter((c) => c.id !== id));
  };

  // Stats
  const total = candidates.length;
  const wrappers = candidates.filter((c) => c.wrapper_warning).length;
  const highFit = candidates.filter((c) => c.inception_fit_score >= 0.65).length;
  const avgFit = total > 0
    ? candidates.reduce((s, c) => s + c.inception_fit_score, 0) / total
    : 0;

  return (
    <div className="min-h-full">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tighter text-text-primary mb-2">
            Pipeline Inception
          </h1>
          <p className="text-text-secondary text-sm max-w-2xl">
            Candidatos qualificados para o programa. Avance o status conforme
            o relacionamento evolui — a cadência de nutrição sugere a
            frequência ideal de contato.
          </p>
        </header>

        {/* Stats bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Total" value={total} icon={Users} />
          <StatCard
            label="Alto fit"
            value={highFit}
            accent="text-accent-green"
            icon={TrendingUp}
          />
          <StatCard
            label="Avg Fit"
            value={`${Math.round(avgFit * 100)}%`}
            icon={Target}
          />
          <StatCard
            label="Wrappers"
            value={wrappers}
            accent={wrappers > 0 ? "text-accent-red" : "text-text-secondary"}
            icon={ShieldAlert}
          />
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mb-5">
          <div className="relative flex-1 max-w-xs">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar startup..."
              className="w-full h-8 pl-9 pr-3 bg-bg-surface border border-border-default rounded
                         text-xs text-text-primary placeholder:text-text-tertiary
                         focus:outline-none focus:border-accent-green"
            />
          </div>
          <div className="flex items-center gap-1 p-0.5 rounded border border-border-subtle bg-bg-surface">
            <FilterButton
              active={filter === "all"}
              onClick={() => setFilter("all")}
              label={`Todos`}
            />
            {STATUS_ORDER.map((s) => (
              <FilterButton
                key={s}
                active={filter === s}
                onClick={() => setFilter(s)}
                label={STATUS_META[s].label}
              />
            ))}
          </div>
        </div>

        {/* Candidates list */}
        {loading ? (
          <div className="space-y-2">
            <div className="skeleton h-24" />
            <div className="skeleton h-24" />
            <div className="skeleton h-24" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-10 text-center">
            <GitBranch size={28} className="text-text-tertiary mx-auto mb-3" />
            <p className="text-sm text-text-secondary mb-1">
              Nenhum candidato neste estágio
            </p>
            <p className="text-xs text-text-tertiary max-w-md mx-auto">
              Use a análise para identificar startups e adicione ao pipeline com
              um clique.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((c) => (
              <CandidateRow
                key={c.id}
                c={c}
                onStatus={(s) => handleStatus(c.id, s)}
                onDelete={() => handleDelete(c.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`h-7 px-2.5 text-xs font-medium rounded transition-colors ${
        active
          ? "bg-accent-green text-text-inverse"
          : "text-text-secondary hover:text-text-primary hover:bg-bg-hover"
      }`}
    >
      {label}
    </button>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  accent = "text-text-primary",
}: {
  label: string;
  value: number | string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  accent?: string;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <Icon size={14} className="text-text-tertiary" strokeWidth={2} />
      </div>
      <p className={`text-2xl font-mono font-semibold tabular-nums ${accent}`}>
        {value}
      </p>
      <p className="text-2xs text-text-tertiary uppercase tracking-widest mt-1">
        {label}
      </p>
    </div>
  );
}

function CandidateRow({
  c,
  onStatus,
  onDelete,
}: {
  c: Candidate;
  onStatus: (s: string) => void;
  onDelete: () => void;
}) {
  const meta = STATUS_META[c.status] || STATUS_META.identificado;
  const fitHigh = c.inception_fit_score >= 0.65;
  const fitMed = c.inception_fit_score >= 0.4;
  return (
    <article className="card card-interactive p-4">
      <div className="flex items-center gap-4">
        {/* Fit score */}
        <div className="shrink-0 w-14 text-center">
          <div
            className={`text-xl font-mono font-semibold tabular-nums ${
              fitHigh
                ? "text-accent-green"
                : fitMed
                  ? "text-accent-amber"
                  : "text-accent-red"
            }`}
          >
            {Math.round(c.inception_fit_score * 100)}
          </div>
          <div className="text-2xs text-text-tertiary uppercase tracking-wider">
            Fit
          </div>
        </div>

        <div className="h-10 w-px bg-border-subtle" />

        {/* Name + meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-text-primary truncate">
              {c.startup_nome}
            </h3>
            {c.wrapper_warning && (
              <span className="badge-wrapper">
                <ShieldAlert size={9} strokeWidth={2.5} className="mr-0.5" />
                Wrapper
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-text-tertiary">
            <span className="font-mono uppercase tracking-wider">
              {c.categoria_ai}
            </span>
            <span>·</span>
            <span>Moat {c.moat_score.toFixed(1)}/5</span>
            <span>·</span>
            <span>Tech {c.tech_score.toFixed(2)}</span>
            <span>·</span>
            <span>Sector {c.sector_score.toFixed(2)}</span>
          </div>
          {c.notes && (
            <p className="text-xs text-text-secondary mt-1.5 line-clamp-1">
              {c.notes}
            </p>
          )}
        </div>

        {/* Cadence */}
        <div className="shrink-0 flex items-center gap-2 text-xs">
          <span
            className={`w-1.5 h-1.5 rounded-full ${CADENCE_DOT[c.nurture_cadence]}`}
          />
          <span className="text-text-secondary">{c.nurture_cadence}</span>
        </div>

        {/* Next action */}
        {c.next_action_date && (
          <div className="shrink-0 text-right">
            <p className="text-2xs text-text-tertiary uppercase tracking-wider">
              {c.next_action_type}
            </p>
            <p className="text-xs text-text-primary font-mono">
              {new Date(c.next_action_date).toLocaleDateString("pt-BR", {
                day: "2-digit",
                month: "2-digit",
              })}
            </p>
          </div>
        )}

        {/* Assigned */}
        {c.assigned_to && (
          <div className="shrink-0 hidden md:flex items-center gap-1.5 text-xs text-text-tertiary">
            <div className="w-5 h-5 rounded-full bg-bg-hover border border-border-default flex items-center justify-center text-2xs font-medium text-text-secondary">
              {c.assigned_to[0]}
            </div>
            <span>{c.assigned_to}</span>
          </div>
        )}

        {/* Status select */}
        <div className="shrink-0">
          <select
            value={c.status}
            onChange={(e) => onStatus(e.target.value)}
            className={`h-7 px-2 text-xs font-medium border rounded ${meta.color}
                       focus:outline-none focus:border-accent-green cursor-pointer`}
          >
            {STATUS_ORDER.map((s) => (
              <option key={s} value={s}>
                {STATUS_META[s].label}
              </option>
            ))}
            {c.status === "declined" && (
              <option value="declined">Declined</option>
            )}
          </select>
        </div>

        {/* Delete */}
        <button
          onClick={onDelete}
          className="shrink-0 p-1.5 text-text-tertiary hover:text-accent-red transition-colors"
          aria-label="Remover"
        >
          <Trash2 size={14} strokeWidth={2} />
        </button>
      </div>
    </article>
  );
}
