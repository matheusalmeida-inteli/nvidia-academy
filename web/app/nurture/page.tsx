"use client";

import { useState, useEffect } from "react";
import {
  HeartHandshake,
  Filter,
  Search,
  Calendar,
  ChevronRight,
  Mail,
  Phone,
  Link,
  CheckCircle2,
  Clock,
  XCircle,
  TrendingUp,
} from "lucide-react";
import { getUpcomingNurture, type Candidate } from "@/lib/api";
import { NurturePanel } from "@/components/NurturePanel";

const CADENCE_META: Record<string, { label: string; color: string; dot: string; desc: string }> = {
  semanal: {
    label: "Semanal",
    color: "text-accent-red",
    dot: "bg-accent-red",
    desc: "Engajamento alto — manter cadência semanal",
  },
  quinzenal: {
    label: "Quinzenal",
    color: "text-accent-amber",
    dot: "bg-accent-amber",
    desc: "Acompanhamento médio — toque a cada 2 semanas",
  },
  mensal: {
    label: "Mensal",
    color: "text-accent-green",
    dot: "bg-accent-green",
    desc: "Relacionamento maduro — cadência mensal",
  },
  inativo: {
    label: "Inativo",
    color: "text-text-tertiary",
    dot: "bg-text-tertiary",
    desc: "Sem ação agendada",
  },
};

export default function NurturePage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    getUpcomingNurture(30)
      .then(setCandidates)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = candidates.filter((c) => {
    if (filter !== "all" && c.nurture_cadence !== filter) return false;
    if (search && !c.startup_nome?.toLowerCase().includes(search.toLowerCase()))
      return false;
    return true;
  });

  const selected = candidates.find((c) => c.id === selectedId);

  // Stats
  const total = candidates.length;
  const semanal = candidates.filter((c) => c.nurture_cadence === "semanal").length;
  const quinzenal = candidates.filter((c) => c.nurture_cadence === "quinzenal").length;
  const mensal = candidates.filter((c) => c.nurture_cadence === "mensal").length;

  return (
    <div className="min-h-full">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tighter text-text-primary mb-2">
            Nutrição de Relacionamento
          </h1>
          <p className="text-text-secondary text-sm max-w-2xl">
            Gestão de cadência, ações de contato e outcomes. Cada interação
            alimenta o histórico e atualiza o status automaticamente.
          </p>
        </header>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatBox
            label="Total na agenda"
            value={total}
            sub="próximos 30 dias"
          />
          <StatBox
            label="Semanal"
            value={semanal}
            accent="text-accent-red"
            dot="bg-accent-red"
          />
          <StatBox
            label="Quinzenal"
            value={quinzenal}
            accent="text-accent-amber"
            dot="bg-accent-amber"
          />
          <StatBox
            label="Mensal"
            value={mensal}
            accent="text-accent-green"
            dot="bg-accent-green"
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
              placeholder="Buscar candidato..."
              className="w-full h-8 pl-9 pr-3 bg-bg-surface border border-border-default rounded
                         text-xs text-text-primary placeholder:text-text-tertiary
                         focus:outline-none focus:border-accent-green"
            />
          </div>
          <div className="flex items-center gap-1 p-0.5 rounded border border-border-subtle bg-bg-surface">
            <FilterChip
              active={filter === "all"}
              onClick={() => setFilter("all")}
              label="Todos"
            />
            {Object.entries(CADENCE_META).map(([k, v]) => (
              <FilterChip
                key={k}
                active={filter === k}
                onClick={() => setFilter(k)}
                label={v.label}
              />
            ))}
          </div>
        </div>

        {loading ? (
          <div className="grid lg:grid-cols-5 gap-4">
            <div className="lg:col-span-2 space-y-2">
              <div className="skeleton h-16" />
              <div className="skeleton h-16" />
              <div className="skeleton h-16" />
            </div>
            <div className="lg:col-span-3 skeleton h-96" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-10 text-center">
            <HeartHandshake size={28} className="text-text-tertiary mx-auto mb-3" />
            <p className="text-sm text-text-secondary mb-1">
              Nenhum candidato com cadência ativa
            </p>
            <p className="text-xs text-text-tertiary max-w-md mx-auto">
              Adicione startups ao pipeline para iniciar a nutrição.
            </p>
          </div>
        ) : (
          <div className="grid lg:grid-cols-5 gap-4">
            {/* Candidate list */}
            <div className="lg:col-span-2 space-y-1.5">
              {filtered.map((c) => (
                <CandidateItem
                  key={c.id}
                  c={c}
                  selected={selectedId === c.id}
                  onClick={() => setSelectedId(selectedId === c.id ? null : c.id)}
                />
              ))}
            </div>

            {/* Nurture panel */}
            <div className="lg:col-span-3">
              {selected ? (
                <div className="card p-0 overflow-hidden sticky top-6">
                  {/* Header */}
                  <div className="px-5 py-4 border-b border-border-subtle bg-bg-raised/50">
                    <p className="text-2xs font-medium text-accent-purple uppercase tracking-widest">
                      Candidato #{selected.id}
                    </p>
                    <h2 className="text-base font-semibold text-text-primary tracking-tight mt-0.5">
                      {selected.startup_nome}
                    </h2>
                    <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-text-tertiary">
                      <span className="font-mono uppercase tracking-wider">
                        {selected.categoria_ai}
                      </span>
                      {selected.wrapper_warning && (
                        <span className="badge-wrapper">Wrapper</span>
                      )}
                      <span>·</span>
                      <span>Fit {Math.round(selected.inception_fit_score * 100)}%</span>
                      {selected.assigned_to && (
                        <>
                          <span>·</span>
                          <span>Assigned {selected.assigned_to}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="p-5">
                    <NurturePanel candidateId={selected.id} />
                  </div>
                </div>
              ) : (
                <div className="card p-12 text-center">
                  <Calendar size={28} className="text-text-tertiary mx-auto mb-3" />
                  <p className="text-sm text-text-secondary mb-1">
                    Selecione um candidato
                  </p>
                  <p className="text-xs text-text-tertiary max-w-xs mx-auto">
                    Clique em um item à esquerda para registrar interações e
                    ver o histórico completo.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  sub,
  accent = "text-text-primary",
  dot,
}: {
  label: string;
  value: number;
  sub?: string;
  accent?: string;
  dot?: string;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-2">
        {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />}
        <p className="text-2xs text-text-tertiary uppercase tracking-widest">
          {label}
        </p>
      </div>
      <p className={`text-2xl font-mono font-semibold tabular-nums ${accent}`}>
        {value}
      </p>
      {sub && <p className="text-2xs text-text-tertiary mt-1">{sub}</p>}
    </div>
  );
}

function FilterChip({
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
          ? "bg-accent-purple text-text-inverse"
          : "text-text-secondary hover:text-text-primary hover:bg-bg-hover"
      }`}
    >
      {label}
    </button>
  );
}

function CandidateItem({
  c,
  selected,
  onClick,
}: {
  c: Candidate;
  selected: boolean;
  onClick: () => void;
}) {
  const cadence = CADENCE_META[c.nurture_cadence] || CADENCE_META.inativo;
  const fitHigh = c.inception_fit_score >= 0.65;
  const fitMed = c.inception_fit_score >= 0.4;
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded border transition-all duration-100 ${
        selected
          ? "bg-accent-purple-dim border-accent-purple/40"
          : "bg-bg-surface border-border-subtle hover:border-border-default hover:bg-bg-raised"
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-sm font-semibold text-text-primary truncate flex-1">
          {c.startup_nome}
        </span>
        <span
          className={`text-base font-mono font-semibold tabular-nums shrink-0 ${
            fitHigh
              ? "text-accent-green"
              : fitMed
                ? "text-accent-amber"
                : "text-accent-red"
          }`}
        >
          {Math.round(c.inception_fit_score * 100)}
        </span>
      </div>
      <div className="flex items-center gap-2 text-2xs">
        <span className={`flex items-center gap-1 ${cadence.color}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${cadence.dot}`} />
          {cadence.label}
        </span>
        {c.next_action_date && (
          <>
            <span className="text-text-tertiary/50">·</span>
            <span className="text-text-tertiary font-mono">
              {c.next_action_type}{" "}
              {new Date(c.next_action_date).toLocaleDateString("pt-BR", {
                day: "2-digit",
                month: "2-digit",
              })}
            </span>
          </>
        )}
      </div>
    </button>
  );
}
