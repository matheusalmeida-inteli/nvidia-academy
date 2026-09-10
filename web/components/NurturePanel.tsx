"use client";

import { useState } from "react";
import {
  ChevronDown,
  Plus,
  Mail,
  Phone,
  Link,
  CheckCircle2,
  Clock,
  XCircle,
  Calendar,
  Send,
} from "lucide-react";
import {
  addNurtureLog,
  getNurtureLog,
  type NurtureLog,
} from "@/lib/api";

const ACTION_TYPES = [
  { value: "email", label: "Email" },
  { value: "call", label: "Call" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "meetup", label: "Meetup" },
  { value: "workshop", label: "Workshop" },
  { value: "gtc", label: "GTC" },
  { value: "demo_day", label: "Demo Day" },
  { value: "introduction", label: "Introdução" },
  { value: "pitch", label: "Pitch" },
  { value: "follow_up", label: "Follow-up" },
];

const CHANNELS = [
  { value: "", label: "(nenhum)" },
  { value: "email", label: "Email" },
  { value: "call", label: "Call" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "in_person", label: "Presencial" },
  { value: "event", label: "Evento" },
  { value: "online", label: "Online" },
];

const OUTCOMES = [
  {
    value: "positive",
    label: "Positivo",
    color: "text-accent-green border-accent-green/30 bg-accent-green-dim",
    icon: CheckCircle2,
  },
  {
    value: "pending",
    label: "Pendente",
    color: "text-accent-amber border-accent-amber/30 bg-accent-amber-dim",
    icon: Clock,
  },
  {
    value: "no_response",
    label: "Sem resposta",
    color: "text-text-tertiary border-border-default bg-bg-surface",
    icon: XCircle,
  },
  {
    value: "negative",
    label: "Negativo",
    color: "text-accent-red border-accent-red/30 bg-accent-red-dim",
    icon: XCircle,
  },
  {
    value: "scheduled",
    label: "Agendado",
    color: "text-accent-purple border-accent-purple/30 bg-accent-purple-dim",
    icon: Calendar,
  },
];

const ACTION_ICON: Record<string, React.ComponentType<any>> = {
  email: Mail,
  call: Phone,
  linkedin: Link,
  meetup: ChevronDown,
  workshop: ChevronDown,
  gtc: ChevronDown,
  demo_day: ChevronDown,
  introduction: ChevronDown,
  pitch: ChevronDown,
  follow_up: ChevronDown,
};

export function NurturePanel({ candidateId }: { candidateId: number }) {
  const [logs, setLogs] = useState<NurtureLog[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [actionType, setActionType] = useState("email");
  const [channel, setChannel] = useState("");
  const [outcome, setOutcome] = useState("pending");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async () => {
    if (!loaded) {
      try {
        const data = await getNurtureLog(candidateId);
        setLogs(data);
        setLoaded(true);
      } catch (e: any) {
        setError(e.message);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const log = await addNurtureLog(candidateId, {
        action_type: actionType,
        channel: channel || undefined,
        outcome,
        notes: notes || undefined,
      });
      setLogs((prev) => [log, ...prev]);
      setNotes("");
      setChannel("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* History */}
      <div>
        <button
          onClick={loadLogs}
          className="flex items-center justify-between w-full mb-2 group"
        >
          <span className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest">
            Histórico {loaded && `(${logs.length})`}
          </span>
          <ChevronDown
            size={12}
            strokeWidth={2.5}
            className={`text-text-tertiary transition-transform ${
              loaded ? "rotate-180" : ""
            } group-hover:text-text-secondary`}
          />
        </button>
        {loaded && logs.length > 0 && (
          <ul className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {logs.map((log) => {
              const ActionIcon = ACTION_ICON[log.action_type] || ChevronDown;
              const out =
                OUTCOMES.find((o) => o.value === log.outcome) || OUTCOMES[1];
              return (
                <li
                  key={log.id}
                  className="flex gap-3 p-2.5 rounded border border-border-subtle bg-bg-base/50"
                >
                  <div className="shrink-0 w-7 h-7 rounded-md bg-bg-hover flex items-center justify-center text-text-secondary">
                    <ActionIcon size={13} strokeWidth={2} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-semibold text-text-primary capitalize">
                        {log.action_type.replace("_", " ")}
                      </span>
                      {log.channel && (
                        <span className="text-2xs text-text-tertiary">
                          via {log.channel}
                        </span>
                      )}
                    </div>
                    {log.notes && (
                      <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">
                        {log.notes}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span
                      className={`text-2xs px-1.5 h-5 inline-flex items-center rounded border ${out.color}`}
                    >
                      {out.label}
                    </span>
                    {log.created_at && (
                      <span className="text-2xs text-text-tertiary font-mono">
                        {new Date(log.created_at).toLocaleDateString("pt-BR", {
                          day: "2-digit",
                          month: "2-digit",
                        })}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {loaded && logs.length === 0 && (
          <p className="text-xs text-text-tertiary italic">
            Nenhuma interação registrada ainda.
          </p>
        )}
      </div>

      {/* Form */}
      <form
        onSubmit={handleSubmit}
        className="pt-5 border-t border-border-subtle space-y-3"
      >
        <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-widest mb-3">
          Nova interação
        </p>
        <div>
          <label className="block text-2xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
            Tipo
          </label>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
            className="select"
          >
            {ACTION_TYPES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-2xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
              Canal
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className="select"
            >
              {CHANNELS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-2xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
              Resultado
            </label>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              className="select"
            >
              {OUTCOMES.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-2xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
            Notas
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Resumo da interação, próximos passos, sentimento..."
            rows={3}
            className="input-textarea"
          />
        </div>

        {error && (
          <p className="text-xs text-accent-red">{error}</p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full h-9 inline-flex items-center justify-center gap-2
                     bg-bg-base border border-accent-purple/40 text-accent-purple
                     text-sm font-medium rounded-md
                     hover:bg-accent-purple-dim hover:border-accent-purple
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors"
        >
          <Send size={13} strokeWidth={2.5} />
          {saving ? "Salvando..." : "Registrar interação"}
        </button>
      </form>
    </div>
  );
}
