const TOKEN_KEY = "tm_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "Request failed";
    if (response.status === 401) setToken(null);
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/api/v1/auth/me"),
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),
  investigations: (params: string) => request<Paged<Investigation>>(`/api/v1/investigations?${params}`),
  createInvestigation: (body: unknown) =>
    request<CreateInvestigationResponse>("/api/v1/investigations", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  investigation: (id: string) => request<Investigation>(`/api/v1/investigations/${id}`),
  archive: (id: string) => request<Investigation>(`/api/v1/investigations/${id}/archive`, { method: "POST" }),
  startJob: (id: string, type: string) =>
    request<{ job_id: string; status: string }>(`/api/v1/investigations/${id}/jobs/${type}`, { method: "POST" }),
  job: (id: string) => request<Job>(`/api/v1/jobs/${id}`),
  cancelJob: (id: string) => request<Job>(`/api/v1/jobs/${id}/cancel`, { method: "POST" }),
  transactions: (id: string, params: string) =>
    request<Paged<ChainTx>>(`/api/v1/investigations/${id}/transactions?${params}`),
  graph: (id: string) => request<GraphPayload>(`/api/v1/investigations/${id}/graph`),
  path: (id: string, source: string, target: string) =>
    request<{ path: string[]; found: boolean }>(
      `/api/v1/investigations/${id}/graph/path?source=${source}&target=${target}`,
    ),
  evidence: (id: string, q = "") =>
    request<{ items: Evidence[] }>(`/api/v1/investigations/${id}/evidence${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  candidates: (id: string) => request<{ items: Candidate[]; disclaimer: string }>(`/api/v1/investigations/${id}/candidates`),
  review: (id: string, body: { decision: string; rationale: string }) =>
    request(`/api/v1/candidates/${id}/review`, { method: "POST", body: JSON.stringify(body) }),
  notes: (id: string) => request<{ items: Note[] }>(`/api/v1/investigations/${id}/notes`),
  addNote: (id: string, body: string) =>
    request(`/api/v1/investigations/${id}/notes`, { method: "POST", body: JSON.stringify({ body }) }),
  audit: (id: string) => request<{ items: Audit[] }>(`/api/v1/investigations/${id}/audit`),
  timeline: (id: string) => request<{ items: TimelineEvent[] }>(`/api/v1/investigations/${id}/timeline`),
  analysis: (id: string) => request<{ payload: AnalysisPayload | null }>(`/api/v1/investigations/${id}/analysis`),
  report: (id: string, fmt: string) =>
    request<{ id: string; format: string; body: string }>(`/api/v1/investigations/${id}/reports/${fmt}`, {
      method: "POST",
    }),
  lookup: (q: string) => request<LookupResponse>(`/api/v1/explorer/lookup?q=${encodeURIComponent(q)}`),
  integrations: () => request<Integrations>("/api/v1/integrations"),
  sources: () => request<{ items: Source[] }>("/api/v1/osint/sources"),
  createSource: (body: unknown) =>
    request("/api/v1/osint/sources", { method: "POST", body: JSON.stringify(body) }),
};

export type User = { id: string; email: string; full_name: string; role: string };
export type Investigation = {
  id: string;
  title: string;
  description: string;
  seed_value: string;
  seed_type: string;
  objective: string;
  status: string;
  max_depth: number;
  max_transactions: number;
  is_fixture: boolean;
  created_at: string;
};
export type Paged<T> = { items: T[]; total: number; page: number; page_size: number };
export type Dashboard = {
  totals: { investigations: number; active: number; completed: number; wallets: number; transactions: number };
  jobs: Job[];
  recent: Investigation[];
  empty: boolean;
};
export type Job = {
  id: string;
  status: string;
  progress: number;
  message: string;
  error?: string | null;
  job_type: string;
  investigation_id?: string | null;
  extra?: Record<string, unknown>;
};
export type CreateInvestigationResponse =
  | { confirmation_required: true; scope: Record<string, unknown> }
  | { investigation: Investigation; job_id: string };
export type ChainTx = {
  tx_hash: string;
  block_number: number | null;
  timestamp: string | null;
  from_address: string;
  to_address: string | null;
  value_wei: string;
  status: string | null;
  is_fixture: boolean;
};
export type GraphPayload = {
  nodes: Array<Record<string, string | number>>;
  edges: Array<Record<string, string | null>>;
  truncated: boolean;
  notice: string;
};
export type Evidence = {
  id: string;
  source_type: string;
  source_url: string;
  indicator: string;
  original_timestamp: string | null;
  collected_at: string;
  extracted_context: string;
  verification_status: string;
  reliability: string;
  notice: string;
};
export type Candidate = {
  id: string;
  wallet_address: string;
  relationship_type: string;
  supporting: Array<{ type: string; text: string }>;
  contradictory: Array<{ type: string; text: string }>;
  temporal_score: number;
  graph_score: number;
  reliability_score: number;
  overall_score: number;
  label: string;
  explanation: string;
  verification_status: string;
  analysis_timestamp: string;
  component_scores: Record<string, number>;
};
export type Note = { id: string; body: string; author_id: string; created_at: string };
export type Audit = { id: string; action: string; actor_id: string | null; details: Record<string, unknown>; created_at: string };
export type TimelineEvent = {
  kind: string;
  source_timestamp: string | null;
  collected_timestamp: string | null;
  label: string;
  ref: string;
};
export type AnalysisPayload = {
  algorithm_version: string;
  temporal: { deltas_seconds: number[]; mean: number | null };
  graph: { nodes: Array<Record<string, unknown>>; notice: string };
  disclaimer: string;
};
export type LookupResponse = { status: string; result?: Record<string, unknown>; error?: string; integrations?: unknown };
export type Integrations = {
  ethereum: { rpc: string; explorer: string; fixture_provider: string; limitations: string[] };
  github: { configured: boolean; authenticated: boolean; rate_limit_note: string };
  threat_feeds: { status: string; allowlist: string[] };
  jobs: { mode: string };
};
export type Source = {
  id: string;
  name: string;
  source_type: string;
  endpoint: string;
  enabled: boolean;
  status: string;
  last_success_at: string | null;
  last_error: string | null;
};
