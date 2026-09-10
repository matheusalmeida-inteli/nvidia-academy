"use client";

import { useState } from "react";
import {
  Building2,
  ShieldAlert,
  Plus,
  Check,
  ChevronDown,
  Briefcase,
  Cpu,
  Users,
  Lightbulb,
  AlertTriangle,
  SearchX,
  Calendar,
} from "lucide-react";
import type { Briefing } from "@/lib/api";
import { createCandidate, getStartupByName } from "@/lib/api";

function fitBucket(s: number): "high" | "medium" | "low" {
  if (s >= 0.65) return "high";
  if (s >= 0.4) return "medium";
  return "low";
}

const FIT_COLOR = {
  high: { text: "text-accent-green", bg: "bg-accent-green", label: "Alto" },
  medium: { text: "text-accent-amber", bg: "bg-accent-amber", label: "Médio" },
  low: { text: "text-accent-red", bg: "bg-accent-red", label: "Baixo" },
};

export function BriefingPanel({ briefing }: { briefing: Briefing }) {
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openSection, setOpenSection] = useState<string | null>("comercial");

  const fit = fitBucket(briefing.inception_fit_score);
  const fitStyle = FIT_COLOR[fit];
  const isEmpty = /Nenhuma startup/.test(briefing.empresa);

  const handleAddToPipeline = async () => {
    setSaving(true);
    setError(null);
    try {
      const startup = await getStartupByName(briefing.empresa);
      if (!startup?.id) {
        setError("Startup não encontrada no banco");
        return;
      }
      await createCandidate({
        startup_id: startup.id,
        notes: `Fit ${Math.round(briefing.inception_fit_score * 100)}% — ${briefing.nurture_suggestion || "Adicionado via análise"}`,
      });
      setSaved(true);
    } catch (e: any) {
      setError(e.message || "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <aside className="sticky top-6 card p-0 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border-subtle bg-bg-raised/50">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-md bg-accent-green-dim shrink-0">
            <Briefcase size={16} className="text-accent-green" strokeWidth={2.5} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-2xs font-medium text-accent-green uppercase tracking-widest">
              Briefing executivo
            </p>
            <h2 className="text-base font-semibold text-text-primary tracking-tight mt-0.5 truncate">
              {briefing.empresa}
            </h2>
            <div className="flex items-center gap-2 mt-1.5 text-xs text-text-tertiary">
              <Building2 size={11} strokeWidth={2} />
              <span>{briefing.setor}</span>
              <span className="text-text-tertiary/50">·</span>
              <span className="font-mono uppercase tracking-wider">
                {briefing.maturidade_ai.replace("_", " ")}
              </span>
              {briefing.evidencia_insuficiente && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium border border-amber-200">evidência baixa</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {isEmpty ? (
        <div className="p-8 flex flex-col items-center text-center gap-3">
          <div className="p-3 rounded-full bg-bg-base/60 border border-border-subtle">
            <SearchX size={20} className="text-text-tertiary" strokeWidth={2} />
          </div>
          <p className="text-sm font-semibold text-text-primary">Nenhuma startup encontrada</p>
          <p className="text-xs text-text-secondary leading-relaxed max-w-xs">
            Tente refinar a query com setor ou estágio específico, ou reformule
            os termos de busca para ampliar a cobertura.
          </p>
        </div>
      ) : (
      <div className="p-5 space-y-5">
        {/* Insufficient evidence warning */}
        {briefing.evidencia_insuficiente && (
          <div className="flex items-start gap-2.5 p-3 rounded-md bg-accent-amber-dim border border-accent-amber/20">
            <AlertTriangle size={14} className="text-accent-amber shrink-0 mt-0.5" strokeWidth={2.5} />
            <div>
              <p className="text-xs font-semibold text-accent-amber">Evidência insuficiente</p>
              <p className="text-2xs text-text-secondary mt-0.5 leading-relaxed">
                Recomendações geradas com base em sinais parciais. Colete métricas
                técnicas (latência, volume, custo) antes de comprometer POCs.
              </p>
            </div>
          </div>
        )}

        {/* Fit score block */}
        <div>
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-xs text-text-secondary">Inception Fit Score</span>
            <span className={`stat-value text-2xl ${fitStyle.text}`}>
              {Math.round(briefing.inception_fit_score * 100)}
              <span className="text-sm text-text-tertiary">%</span>
            </span>
          </div>
          <div className="relative h-1.5 bg-bg-base rounded-full overflow-hidden">
            <div
              className={`absolute inset-y-0 left-0 ${fitStyle.bg} rounded-full transition-all duration-500`}
              style={{ width: `${briefing.inception_fit_score * 100}%` }}
            />
          </div>
          <p className="text-2xs text-text-tertiary mt-1.5">
            {fitStyle.label} fit · score baseado em tech, sector, traction e moat
          </p>
        </div>

        {/* Wrapper warning */}
        {briefing.wrapper_warning && (
          <div className="flex items-start gap-2.5 p-3 rounded-md bg-accent-red-dim border border-accent-red/20">
            <ShieldAlert size={14} className="text-accent-red shrink-0 mt-0.5" strokeWidth={2.5} />
            <div>
              <p className="text-xs font-semibold text-accent-red">Wrapper de LLM</p>
              <p className="text-2xs text-text-secondary mt-0.5 leading-relaxed">
                Defensibilidade baixa. Foco em nutrir com educação em
                modelo próprio + dados proprietários antes de abordagem
                comercial agressiva.
              </p>
            </div>
          </div>
        )}

        {/* Nurture suggestion */}
        {briefing.nurture_suggestion && (
          <div className="p-3 rounded-md bg-bg-base/60 border border-border-subtle">
            <div className="flex items-start gap-2">
              <Lightbulb
                size={12}
                className="text-accent-amber shrink-0 mt-0.5"
                strokeWidth={2.5}
              />
              <div>
                <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest mb-1">
                  Sugestão de cadência
                </p>
                <p className="text-xs text-text-primary leading-relaxed">
                  {briefing.nurture_suggestion}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Action sections */}
        <div className="space-y-1.5">
          <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest mb-2">
            Próximas ações
          </p>
          <ActionSection
            id="comercial"
            label="Comercial"
            icon={Briefcase}
            color="green"
            items={briefing.proximos_comerciais}
            open={openSection === "comercial"}
            onToggle={(id) => setOpenSection(openSection === id ? null : id)}
          />
          <ActionSection
            id="tecnico"
            label="Técnico"
            icon={Cpu}
            color="blue"
            items={briefing.proximos_tecnicos}
            open={openSection === "tecnico"}
            onToggle={(id) => setOpenSection(openSection === id ? null : id)}
          />
          <ActionSection
            id="comunitario"
            label="Comunitário"
            icon={Users}
            color="purple"
            items={briefing.proximos_comunitarios}
            open={openSection === "comunitario"}
            onToggle={(id) => setOpenSection(openSection === id ? null : id)}
          />
        </div>

        {/* Fit breakdown */}
        {Object.keys(briefing.fit_breakdown || {}).length > 0 && (
          <div>
            <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest mb-2">
              Decomposição do fit
            </p>
            <ul className="space-y-1.5">
              {Object.entries(briefing.fit_breakdown).map(([k, v]) => {
                const score = typeof v === "number" ? v : 0;
                return (
                  <li key={k} className="flex items-center gap-3">
                    <span className="text-xs text-text-secondary capitalize w-20 shrink-0">
                      {k}
                    </span>
                    <div className="flex-1 h-1 bg-bg-base rounded-full overflow-hidden">
                      <div
                        className={`h-full ${
                          score >= 0.7
                            ? "bg-accent-green"
                            : score >= 0.4
                              ? "bg-accent-amber"
                              : "bg-accent-red"
                        } rounded-full transition-all duration-300`}
                        style={{ width: `${score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-text-primary w-9 text-right tabular-nums">
                      {Math.round(score * 100)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Add to pipeline */}
        <button
          onClick={handleAddToPipeline}
          disabled={saving || saved}
          className="w-full h-9 inline-flex items-center justify-center gap-2
                     bg-bg-base border border-accent-green/40 text-accent-green
                     text-sm font-medium rounded-md
                     hover:bg-accent-green-dim hover:border-accent-green
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all duration-150"
        >
          {saved ? (
            <>
              <Check size={14} strokeWidth={2.5} />
              Adicionado ao pipeline
            </>
          ) : saving ? (
            "Salvando..."
          ) : (
            <>
              <Plus size={14} strokeWidth={2.5} />
              Adicionar ao pipeline
            </>
          )}
        </button>
        {error && (
          <p className="text-xs text-accent-red -mt-3">{error}</p>
        )}

        {/* Sources */}
        {briefing.fontes_consultadas.length > 0 && (
          <div>
            <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest mb-2">
              Fontes NVIDIA consultadas
            </p>
            <ul className="space-y-1">
              {briefing.fontes_consultadas.slice(0, 3).map((f, i) => (
                <li key={i}>
                  <a
                    href={f}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-text-tertiary hover:text-accent-green transition-colors truncate block"
                  >
                    {f}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-2xs text-text-tertiary pt-3 border-t border-border-subtle flex items-center gap-1.5">
          <Calendar size={11} strokeWidth={2} />
          {new Date(briefing.generated_at).toLocaleString("pt-BR", {
            dateStyle: "short",
            timeStyle: "short",
          })}
        </p>
      </div>
      )}
    </aside>
  );
}

function ActionSection({
  id,
  label,
  icon: Icon,
  color,
  items,
  open,
  onToggle,
}: {
  id: string;
  label: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  color: "green" | "blue" | "purple";
  items: string[];
  open: boolean;
  onToggle: (id: string) => void;
}) {
  const colorMap = {
    green: "text-accent-green bg-accent-green-dim border-accent-green/30",
    blue: "text-accent-blue bg-accent-blue-dim border-accent-blue/30",
    purple: "text-accent-purple bg-accent-purple-dim border-accent-purple/30",
  };
  const dotMap = {
    green: "bg-accent-green",
    blue: "bg-accent-blue",
    purple: "bg-accent-purple",
  };

  return (
    <div className={`rounded border ${colorMap[color]} overflow-hidden`}>
      <button
        onClick={() => onToggle(id)}
        className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-bg-base/40 transition-colors"
      >
        <Icon size={13} strokeWidth={2.5} />
        <span className="text-xs font-semibold flex-1 text-left">{label}</span>
        <span className="text-2xs text-text-tertiary font-mono tabular-nums">
          {items.length}
        </span>
        <ChevronDown
          size={12}
          strokeWidth={2.5}
          className={`text-text-tertiary transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && items.length > 0 && (
        <ul className="px-3 py-2.5 space-y-1.5 bg-bg-base/40 border-t border-border-subtle">
          {items.map((item, i) => (
            <li key={i} className="flex gap-2 text-xs text-text-primary leading-relaxed">
              <span className={`w-1 h-1 rounded-full ${dotMap[color]} mt-1.5 shrink-0`} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
