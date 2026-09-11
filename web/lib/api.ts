export interface Recommendation {
  tecnologia: string;
  justificativa_tecnica: string;
  justificativa_negocio: string;
  prioridade: string;
  complexidade: string;
  proxima_acao: string;
  evidencias?: string[];
  fontes_rag?: Array<{ titulo?: string; url?: string }>;
  origem_recomendacao?: "rag" | "regra_de_negocio" | "rag_e_regra" | "fraca" | string;
  score_final?: number;
  score_breakdown?: { rag?: number; hardcoded?: number; sector?: number };
  regra_ids?: string[];
}

export interface Briefing {
  empresa: string;
  setor: string;
  maturidade_ai: string;
  score_maturidade: number;
  inception_fit_score: number;
  wrapper_warning: boolean;
  evidencia_insuficiente?: boolean;
  fit_breakdown: Record<string, number>;
  criterio_selecao?: string;
  nurture_suggestion: string;
  recomendacoes: Recommendation[];
  proximos_comerciais: string[];
  proximos_tecnicos: string[];
  proximos_comunitarios: string[];
  fontes_consultadas: string[];
  generated_at: string;
}

export interface StartupResult {
  nome: string;
  site: string | null;
  setor: string | null;
  estagio: string;
  localizacao: string | null;
  descricao_curta: string | null;
  categoria: string;
  confianca: number;
  inception_fit_score: number;
  wrapper_warning: boolean;
  moat_score: number;
  evidencias_count: number;
  recomendacoes: Recommendation[];
}

export interface QueryResponse {
  startups: StartupResult[];
  briefing: Briefing | null;
  query_keywords: string[];
  total_found: number;
}

export interface Candidate {
  id: number;
  startup_id: number;
  startup_nome: string | null;
  inception_fit_score: number;
  status: string;
  categoria_ai: string;
  wrapper_warning: boolean;
  fit_justification: string | null;
  moat_score: number;
  tech_score: number;
  sector_score: number;
  traction_score: number;
  nurture_cadence: string;
  next_action_date: string | null;
  next_action_type: string | null;
  next_action_desc: string | null;
  notes: string | null;
  assigned_to: string | null;
  last_contacted_at: string | null;
  last_contacted_type: string | null;
  created_at: string | null;
}

export interface NurtureLog {
  id: number;
  candidate_id: number;
  action_type: string;
  channel: string | null;
  outcome: string | null;
  notes: string | null;
  created_at: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function submitQuery(
  query: string,
  max_startups = 10,
): Promise<QueryResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90_000);
  try {
    const res = await fetch(`${API_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, max_startups }),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) {
      const text = await res.text();
      let msg = `Query failed: ${res.status} — ${text}`;
      if (res.status === 422) {
        try {
          const data = JSON.parse(text);
          const detail = data?.detail?.[0]?.msg;
          msg = detail
            ? `Consulta inválida: ${detail}`
            : "Consulta inválida. Digite uma descrição com ao menos uma palavra.";
        } catch {
          msg = "Consulta inválida. Digite uma descrição com ao menos uma palavra.";
        }
      } else if (res.status >= 500) {
        msg = "Erro no pipeline (servidor). Tente novamente em instantes.";
      }
      throw new Error(msg);
    }
    return res.json();
  } catch (e: unknown) {
    clearTimeout(timeout);
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error("Tempo limite atingido (90s). Tente uma consulta mais específica.");
    }
    throw e;
  }
}

export async function exportBriefing(
  query: string,
  max_startups = 10,
): Promise<void> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90_000);
  try {
    const res = await fetch(`${API_URL}/query/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, max_startups }),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) {
      throw new Error(`Export failed: ${res.status} — ${await res.text()}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "briefing_nvidia_radar.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e: unknown) {
    clearTimeout(timeout);
    throw e;
  }
}

export async function listStartups(
  opts: {
    setor?: string;
    estagio?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<{ startups: any[]; total: number }> {
  const params = new URLSearchParams();
  if (opts.setor) params.set("setor", opts.setor);
  if (opts.estagio) params.set("estagio", opts.estagio);
  if (opts.search) params.set("search", opts.search);
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.offset) params.set("offset", String(opts.offset));
  const res = await fetch(`${API_URL}/startups?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to list startups");
  return res.json();
}

export async function getStartupByName(nome: string): Promise<any | null> {
  const res = await fetch(`${API_URL}/startups?search=${encodeURIComponent(nome)}&limit=1`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.startups?.[0] || null;
}

// ---- Candidates ----

export async function listCandidates(
  opts: { status?: string; categoria_ai?: string; assigned_to?: string } = {},
): Promise<Candidate[]> {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.categoria_ai) params.set("categoria_ai", opts.categoria_ai);
  if (opts.assigned_to) params.set("assigned_to", opts.assigned_to);
  const res = await fetch(`${API_URL}/candidates?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to list candidates");
  return res.json();
}

export async function getCandidate(id: number): Promise<Candidate> {
  const res = await fetch(`${API_URL}/candidates/${id}`);
  if (!res.ok) throw new Error("Candidate not found");
  return res.json();
}

export async function createCandidate(
  body: {
    startup_id: number;
    notes?: string;
    assigned_to?: string;
    inception_fit_score?: number;
    categoria_ai?: string;
    wrapper_warning?: boolean;
    moat_score?: number;
    tech_score?: number;
    sector_score?: number;
    traction_score?: number;
    nurture_cadence?: string;
    next_action_date?: string;
    next_action_type?: string;
    next_action_desc?: string;
  },
): Promise<Candidate> {
  const res = await fetch(`${API_URL}/candidates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create candidate");
  return res.json();
}

export async function updateCandidate(
  id: number,
  body: Partial<{
    status: string;
    notes: string;
    assigned_to: string;
    next_action_date: string | null;
    next_action_type: string;
    next_action_desc: string;
    nurture_cadence: string;
  }>,
): Promise<Candidate> {
  const res = await fetch(`${API_URL}/candidates/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update candidate");
  return res.json();
}

export async function deleteCandidate(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/candidates/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete candidate");
}

// ---- Nurture ----

export async function getUpcomingNurture(days = 30): Promise<Candidate[]> {
  const res = await fetch(`${API_URL}/nurture/upcoming?days=${days}`);
  if (!res.ok) throw new Error("Failed to list upcoming nurture");
  return res.json();
}

export async function addNurtureLog(
  candidateId: number,
  body: {
    action_type: string;
    channel?: string;
    outcome?: string;
    notes?: string;
  },
): Promise<NurtureLog> {
  const res = await fetch(`${API_URL}/candidates/${candidateId}/nurture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to add nurture log");
  return res.json();
}

export async function getNurtureLog(candidateId: number): Promise<NurtureLog[]> {
  const res = await fetch(`${API_URL}/candidates/${candidateId}/nurture`);
  if (!res.ok) throw new Error("Failed to get nurture log");
  return res.json();
}
