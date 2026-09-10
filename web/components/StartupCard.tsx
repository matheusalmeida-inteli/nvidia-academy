"use client";

import {
  Building2,
  MapPin,
  Layers,
  ExternalLink,
  Sparkles,
  ShieldAlert,
  ArrowUpRight,
  CheckCircle2,
} from "lucide-react";
import type { StartupResult } from "@/lib/api";

const CATEGORIA_BADGE: Record<string, string> = {
  ai_native: "badge-ai-native",
  ai_enabled: "badge-ai-enabled",
  wrapper_llm: "badge-wrapper",
  non_ai: "badge-non-ai",
};

const CATEGORIA_LABEL: Record<string, string> = {
  ai_native: "AI-Native",
  ai_enabled: "AI-Enabled",
  wrapper_llm: "Wrapper",
  non_ai: "Non-AI",
};

function fitBucket(score: number): "high" | "medium" | "low" {
  if (score >= 0.65) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

const FIT_LABEL: Record<string, string> = {
  high: "Alto",
  medium: "Médio",
  low: "Baixo",
};

export function StartupCard({ startup }: { startup: StartupResult }) {
  const cat = CATEGORIA_LABEL[startup.categoria] || startup.categoria;
  const badgeClass = CATEGORIA_BADGE[startup.categoria] || "badge-non-ai";
  const fit = fitBucket(startup.inception_fit_score);

  return (
    <article
      className={`card card-interactive p-5 ${
        startup.wrapper_warning ? "border-accent-red/30" : ""
      }`}
    >
      {/* Wrapper warning */}
      {startup.wrapper_warning && (
        <div className="mb-4 flex items-start gap-2.5 p-3 rounded-md bg-accent-red-dim border border-accent-red/20">
          <ShieldAlert size={14} className="text-accent-red shrink-0 mt-0.5" strokeWidth={2.5} />
          <div>
            <p className="text-xs font-semibold text-accent-red">
              TAPI §3 — Wrapper de LLM detectado
            </p>
            <p className="text-2xs text-text-secondary mt-0.5 leading-relaxed">
              Dependência significativa de APIs externas (OpenAI/Anthropic)
              sem dados proprietários ou modelo próprio. Alto risco de
              commoditização.
            </p>
          </div>
        </div>
      )}

      {/* Header row: name + fit */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <h3 className="text-base font-semibold text-text-primary tracking-tight truncate">
              {startup.nome}
            </h3>
            {startup.site && (
              <a
                href={startup.site}
                target="_blank"
                rel="noreferrer"
                className="text-text-tertiary hover:text-accent-green transition-colors shrink-0"
                aria-label={`Abrir ${startup.nome}`}
              >
                <ArrowUpRight size={14} strokeWidth={2} />
              </a>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-tertiary">
            {startup.setor && (
              <span className="flex items-center gap-1">
                <Building2 size={11} strokeWidth={2} />
                {startup.setor}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Layers size={11} strokeWidth={2} />
              {startup.estagio}
            </span>
            {startup.localizacao && (
              <span className="flex items-center gap-1">
                <MapPin size={11} strokeWidth={2} />
                {startup.localizacao}
              </span>
            )}
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className="flex items-baseline gap-1.5">
            <span
              className={`text-2xl font-mono font-semibold tabular-nums ${
                fit === "high"
                  ? "text-accent-green"
                  : fit === "medium"
                    ? "text-accent-amber"
                    : "text-accent-red"
              }`}
            >
              {Math.round(startup.inception_fit_score * 100)}
            </span>
            <span className="text-xs text-text-tertiary font-mono">%</span>
          </div>
          <p className="text-2xs text-text-tertiary uppercase tracking-wider mt-0.5">
            Inception Fit
          </p>
        </div>
      </div>

      {/* Description */}
      {startup.descricao_curta && (
        <p className="text-sm text-text-secondary leading-relaxed mb-4 line-clamp-2">
          {startup.descricao_curta}
        </p>
      )}

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <MetricCell
          label="Categoria"
          value={cat}
          badgeClass={badgeClass}
        />
        <MetricCell
          label="Moat"
          value={startup.moat_score.toFixed(1)}
          unit="/5"
        />
        <MetricCell
          label="Confiança"
          value={Math.round(startup.confianca * 100).toString()}
          unit="%"
        />
      </div>

      {/* Top recommendations */}
      {startup.recomendacoes.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest">
              Recomendações NVIDIA
            </h4>
            <span className="text-2xs text-text-tertiary">
              {startup.recomendacoes.length} techs
            </span>
          </div>
          <ul className="space-y-1.5">
            {startup.recomendacoes.slice(0, 3).map((r) => (
              <li
                key={r.tecnologia}
                className="flex items-start gap-2.5 p-2.5 rounded
                           bg-bg-base/60 border border-border-subtle"
              >
                <Sparkles
                  size={12}
                  className="text-accent-green mt-0.5 shrink-0"
                  strokeWidth={2.5}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-semibold text-text-primary">
                      {r.tecnologia}
                    </span>
                    <PriorityDot priority={r.prioridade} />
                  </div>
                  <p className="text-xs text-text-secondary leading-snug line-clamp-1">
                    {r.justificativa_tecnica}
                  </p>
                  {r.fontes_rag && r.fontes_rag.length > 0 && (
                    <div className="flex items-center gap-1.5 mt-1">
                      {r.fontes_rag.slice(0, 2).map((f, i) =>
                        f?.url ? (
                          <a
                            key={i}
                            href={f.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-2xs text-accent-green hover:underline truncate"
                            title={f.titulo || f.url}
                          >
                            {f.titulo || f.url}
                          </a>
                        ) : (
                          <span
                            key={i}
                            className="text-2xs text-text-tertiary truncate"
                          >
                            {f.titulo || f.url}
                          </span>
                        ),
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between text-2xs text-text-tertiary">
        <span className="flex items-center gap-1">
          <CheckCircle2 size={11} strokeWidth={2.5} className="text-accent-green" />
          {startup.evidencias_count} evidência(s) verificada(s)
        </span>
      </div>
    </article>
  );
}

function MetricCell({
  label,
  value,
  unit,
  badgeClass,
}: {
  label: string;
  value: string;
  unit?: string;
  badgeClass?: string;
}) {
  return (
    <div className="px-3 py-2 rounded bg-bg-base/60 border border-border-subtle">
      <p className="text-2xs text-text-tertiary uppercase tracking-wider mb-1">
        {label}
      </p>
      {badgeClass ? (
        <span className={badgeClass}>{value}</span>
      ) : (
        <p className="text-sm font-mono font-semibold tabular-nums text-text-primary">
          {value}
          {unit && (
            <span className="text-2xs text-text-tertiary font-normal ml-0.5">
              {unit}
            </span>
          )}
        </p>
      )}
    </div>
  );
}

function PriorityDot({ priority }: { priority: string }) {
  const color =
    priority === "high"
      ? "bg-accent-green"
      : priority === "medium"
        ? "bg-accent-amber"
        : "bg-text-tertiary";
  return (
    <span className="inline-flex items-center gap-1 text-2xs uppercase tracking-wider text-text-tertiary">
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      {priority}
    </span>
  );
}
