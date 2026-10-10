import { storedLocale } from "./i18n";

// Thin client for the Decision Layer REST API (proxied at /api by next.config.mjs).
// The optional bearer token is passed through to the semantic layer (ADR-024);
// without it the API falls back to its service credentials (local/dev only).

export type Kind = "measure" | "dimension" | "time_dimension";

export interface SemanticObject {
  ref: string;
  kind: Kind;
  data_type: string;
  title: string;
  description?: string | null;
  metric_kind?: string | null;
  ratio_parts?: [string, string] | null;
  entity?: string | null;
  dimension_refs?: string[];
  time_dimension?: string | null;
  count_measure?: string | null;
  metadata?: Record<string, unknown>;
  public: boolean;
}

export interface SemanticCatalog {
  provider: string;
  instance: string;
  objects: SemanticObject[];
  hierarchies: Record<string, string[]>;
  discovered_at: string;
}

export interface RoleSpec {
  label?: string;
  default_binding?: "primary_metric" | "preferred_dimensions" | "unit_count" | null;
  editor_parameter?: string | null;
  exclusive_group?: string | null;
  ui_group?: "basic" | "options";
  kind: Kind | "entity";
  metric_kinds?: string[] | null;
  required: boolean;
  multiple: boolean;
  description: string;
}

export interface ParamSpec {
  type: string;
  enum?: string[] | null;
  default?: unknown;
  required: boolean;
  minimum?: number | null;
  maximum?: number | null;
  description: string;
  ui_group?: "basic" | "advanced" | "options" | "hidden";
  label?: string;
  meaning?: "analysis_scope" | "comparison_subject" | "comparison_population" | "period" | "option";
  semantic_kind?: Kind | null;
  semantic_role?: string | null;
  source_policy?: { allowed: ("literal" | "input" | "step")[]; default: "literal" | "previous_result" | "parameter_parents" | "runtime_input"; project: "path" | "condition" | "parents"; parameter?: string | null } | null;
  visible_when?: { parameter: string; equals: string | boolean | number } | null;
}

export interface MethodManifest {
  provides?: string[];
  label?: string;
  name: string;
  version: string;
  kind: string;
  description: string;
  roles: Record<string, RoleSpec>;
  parameters: Record<string, ParamSpec>;
  execution: string;
  interpretation: string;
  outputs: string[];
  selection_outputs?: string[];
  requires_period?: boolean;
}

export interface Artifact { type: string; title?: string | null; data: unknown }
export interface Validation { validator: string; status: "pass" | "warning" | "fail"; code: string; message: string; details?: Record<string, unknown> }

export interface Result {
  provides?: string[];
  status: "success" | "needs_input" | "refused" | "failed";
  interpretation?: string | null;
  primary?: Artifact | null;
  artifacts: Artifact[];
  warnings: string[];
  validation: Validation[];
  needs_input?: { question: string; field: string; candidates: { value: unknown; label: string; count?: number }[] } | null;
  provenance: { method?: string | null; recipe?: string | null; runtime?: Record<string, string>; semantic_refs: string[]; queries: { provider?: string; instance?: string; native_query: unknown; compiled_sql?: unknown; rows: number; elapsed_ms: number }[] };
  run_id?: string | null;
  selections?: Record<string, { complete: boolean; rank_by: string; direction: string; candidates: { path: { member: string; value: unknown }[]; score: number }[] }>;
}

export interface PlanStep { id?: string | null; method: string; method_version?: string | null; purpose?: string | null; purpose_context?: "procedure" | "source_run" | null; goal_ids?: string[]; exploration?: boolean; bindings: Record<string, unknown>; params: Record<string, unknown> }

export interface Recipe {
  name: string;
  version: string;
  description: string;
  status?: "draft" | "published";
  origin_runs?: string[];
  source_question?: string | null;
  default_scope?: { date_range?: [string, string] | null; time_dimension?: string | null; period?: PeriodChoice | null } | null;
  inputs?: Record<string, ParamSpec>;
  routing: { objective?: string; use_for: string[]; do_not_use_for: string[] };
  semantic_scope: { primary_metric: string; related_metrics: string[]; preferred_dimensions: string[]; required_filters: unknown[] };
  mode: "pipeline" | "investigation";
  steps: PlanStep[];
  allowed_methods: string[];
  method_parameters?: Record<string, { fixed: Record<string, unknown>; runtime_allowed?: string[] | null }>;
  limits: { max_steps: number; max_queries: number };
  validators: { name: string }[];
  instructions?: string | null;
}

export interface RecipeCandidate { recipe: Recipe; source_run_id: string; selected_steps: number[]; review_notes: string[] }

export interface Running { run_id: string; status: "running"; running: { kind: string; method?: string | null; started_at: string } | null; poll: string }

export function isRunning(x: unknown): x is Running {
  return !!x && typeof x === "object" && (x as Running).status === "running";
}

/** Poll a run's result until its background job finishes (202 → 200 or an error). */
export async function resultWhenDone(runId: string, onTick?: (seconds: number) => void): Promise<Result> {
  const started = Date.now();
  for (;;) {
    const r = await api<Result | Running>(`/runs/${runId}/result`);
    if (!isRunning(r)) return r;
    onTick?.(Math.round((Date.now() - started) / 1000));
    await new Promise((ok) => setTimeout(ok, 1500));
  }
}

export interface Run {
  remediations?: RunRemediation[];
  retry_of?: { run_id: string; remediation_id: string; checked_at: string } | null;
  goals?: AnalysisGoal[];
  recipe_selection?: { reason: string; goal_ids: string[] } | null;
  recipe_review?: { recipe: string; decision: "selected" | "skipped"; reason: string }[];
  recipe_candidates?: { recipe: string; name?: string }[];
  recipe_invocation?: { id: string; recipe: string; goal_ids: string[]; step_ids: string[]; completed: boolean } | null;
  id: string;
  origin?: "unknown" | "python" | "api" | "web" | "mcp";
  preview?: boolean;
  plan: { question?: string | null; scope: Scope; recipe?: string | null; resolved?: Record<string, string> };
  recipe_snapshot?: Recipe | null;
  steps: { step: PlanStep; method: string; result: Result; started_at: string; finished_at: string;
    requested_step?: PlanStep | null; input_resolutions?: { field: string; source: Record<string, unknown>; resolved: unknown }[];
    parameter_sources?: Record<string, "method_default" | "recipe" | "recipe_fixed" | "request">; author?: ExecutionAuthor | null; invocation_id?: string | null }[];
  caller: { subject?: string | null; groups: string[] };
  shared_with: string[];
  status: "open" | "completed" | "failed";
  running?: { kind: string; method?: string | null; started_at: string } | null;
  error?: { code: string; message: string } | null;
  needs_input?: { field: string; reason_code?: string; question: string; allow_all?: boolean; max_period_days?: number } | null;
  pending_execution?: { kind: string; step?: PlanStep; step_index?: number } | null;
  scope_revision?: number;
  scope_resolution?: { source?: string; source_trust?: string; requested?: PeriodChoice; resolved_at?: string; policy_revision?: string };
  validation: Validation[];
  summary?: string | null;
  conclusion?: { source?: "caller" | "execution"; answer: string; findings: { text: string; step_indices: number[] }[]; limitations: string[]; goal_outcomes?: GoalOutcome[] } | null;
  author?: ExecutionAuthor | null;
  conclusion_author?: ExecutionAuthor | null;
  created_at: string;
  finished_at?: string | null;
}

export interface AnalysisGoal { id: string; description: string; semantic_refs: string[]; required_capabilities: string[]; interpretation: string }
export interface SemanticRequirement { description: string; kind: Kind; ref?: string | null; data_type?: string | null; metric_kind?: string | null; needs_entity?: boolean; needs_time?: boolean }
export interface RunRemediation {
  id: string; goal_id: string; reason: string; evidence: string; proposal: string;
  requirements: SemanticRequirement[]; revision: number; status: "proposed" | "confirmed" | "dismissed";
  model_drafts?: { provider: "cube" | "dbt"; title: string; yaml: string; unresolved: string[]; basis: string[] }[];
  related_goal_ids?: string[];
  checks: { at: string; revision: number; ready: boolean; results: { description: string; ref?: string | null; title?: string | null; issues: string[] }[] }[];
  events: { action: string; at: string; note?: string; run_id?: string }[];
}
export interface GoalOutcome { goal_id: string; status: "supported" | "needs_input" | "unsupported" | "blocked" | "inconclusive"; step_indices: number[]; reason: string; reason_code?: string | null }

export interface ExecutionAuthor {
  client_name?: string | null; client_version?: string | null;
  client_source?: "protocol" | "client_reported" | "runner";
  model_provider?: string | null; model_id?: string | null; model_revision?: string | null;
  model_source?: "client_reported" | "runner";
}

export interface PeriodChoice { mode: "range" | "all" | "relative" | "unresolved"; date_range?: [string, string] | null; preset?: "last_complete_month" | "last_n_days" | null; days?: number | null; timezone?: string; source?: "caller" | "conversation" | "ai_proposal" }
export interface Scope { period?: PeriodChoice | null; date_range?: [string, string] | null; time_dimension?: string | null; filters?: unknown[]; inputs?: Record<string, unknown> }

export interface SourceConfig {
  provider: "cube" | "dbt";
  environment_id?: number | null;
  instance: string;
  api_url: string;
  auth_method: "token" | "api_secret" | "none";
  api_secret_configured: boolean;
  service_groups: string[];
  environment_overrides: Record<string, boolean>;
  service_credentials_allowed: boolean;
  admin_configured: boolean;
  admin_required: boolean;
  editable: boolean;
  encryption_configured: boolean;
}
export interface SourceTestResult {
  status: "connected";
  provider: string;
  instance: string;
  objects: number;
  measures: number;
  dimensions: number;
  time_dimensions: number;
  api_url?: string;
  has_metrics?: boolean;
}
export interface ReadinessMetric {
  metric: SemanticObject & { entity?: string | null };
  checks: {
    decomposition: { status: "ready" | "missing" | "not_applicable"; parts: string[]; impact: string | null };
    time: { status: "ready" | "unknown" | "missing"; dimensions: string[]; impact: string | null };
    entity_key: { status: "ready" | "missing"; ref: string | null; impact: string | null };
  };
}
export interface SourceReadiness { provider: string; instance: string; metrics: ReadinessMetric[]; note: string }

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

const SOURCE_ADMIN_KEY = "decision-layer.source-admin-key";
const SOURCE_CALLER_TOKEN = "decision-layer.source-caller-token";
const TOKEN_KEY = "decision-layer.token";
const OLD_TOKEN_KEY = "analytica.token";   // before the rename

export function getToken(): string {
  try {
    return sessionStorage.getItem(SOURCE_CALLER_TOKEN) || localStorage.getItem(TOKEN_KEY) || localStorage.getItem(OLD_TOKEN_KEY) || "";
  } catch { return ""; }
}

export function setToken(token: string): void {
  setSourceCallerToken(token);
  try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(OLD_TOKEN_KEY); } catch { /* private mode */ }
}

export function getSourceAdminKey(): string {
  try { return sessionStorage.getItem(SOURCE_ADMIN_KEY) || ""; } catch { return ""; }
}

export function setSourceAdminKey(key: string): void {
  try { key ? sessionStorage.setItem(SOURCE_ADMIN_KEY, key) : sessionStorage.removeItem(SOURCE_ADMIN_KEY); } catch { /* private mode */ }
}

export function getSourceCallerToken(): string {
  try { return sessionStorage.getItem(SOURCE_CALLER_TOKEN) || localStorage.getItem(TOKEN_KEY) || localStorage.getItem(OLD_TOKEN_KEY) || ""; } catch { return ""; }
}

export function setSourceCallerToken(token: string): void {
  try { token ? sessionStorage.setItem(SOURCE_CALLER_TOKEN, token) : sessionStorage.removeItem(SOURCE_CALLER_TOKEN); } catch { /* private mode */ }
}

export async function api<T>(path: string, init?: { method?: string; body?: unknown; admin?: boolean; callerToken?: string }): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", "X-Decision-Layer-Client": "web" };
  headers["Accept-Language"] = storedLocale();
  const token = init?.callerToken ?? getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init?.admin) {
    const key = getSourceAdminKey();
    if (key) headers["X-Decision-Layer-Admin-Key"] = key;
  }
  const resp = await fetch(`/api${path}`, {
    method: init?.method || (init?.body ? "POST" : "GET"),
    headers,
    body: init?.body ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const e = body?.error;
    const msg = e?.message ?? (Array.isArray(body?.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : resp.statusText);
    throw new ApiError(resp.status, e?.code ?? String(resp.status), msg, e?.details ?? body?.detail);
  }
  return body as T;
}
