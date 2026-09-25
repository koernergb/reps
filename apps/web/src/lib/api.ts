export type ApiError = { code: string; message: string; request_id: string };

export class ApiRequestError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.code = error.code;
    this.status = status;
    this.requestId = error.request_id;
  }
}

export type HealthResponse = {
  status: "ok" | "degraded";
  service: string;
  version: string;
  request_id: string;
};

export type CapabilitySummary = {
  slug: string;
  name: string;
  capability_type: string;
  weight: number;
};

export type ProblemSummary = {
  id: string;
  slug: string;
  title: string;
  difficulty: "easy" | "medium" | "hard";
  language: string;
  status: "development" | "reviewed";
  topic: { slug: string; name: string } | null;
  capabilities: CapabilitySummary[];
};

export type TestCase = { id?: string; args: unknown[]; expected: unknown };

export type ProblemDetail = ProblemSummary & {
  statement: string;
  examples: Array<{ input: Record<string, unknown>; output: unknown; explanation?: string }>;
  constraints: string[];
  starter_code: string;
  visible_tests: TestCase[];
};

export type VisibleTestResult = {
  id: string;
  args: unknown[];
  expected: unknown;
  actual: unknown;
  status: "passed" | "wrong_answer" | "error" | "timeout" | "memory_limit" | "output_limit" | "crashed" | "not_run";
  error: string | null;
  stdout: string | null;
  duration_ms: number | null;
};

export type ExecutionResult = {
  verdict: string | null;
  message: string;
  visible?: VisibleTestResult[];
  visible_passed?: number;
  visible_total?: number;
  hidden?: { passed: number; total: number; failures: Record<string, number> };
};

export type Execution = {
  id: string;
  kind: "run" | "submit";
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "expired";
  problem_slug: string;
  verdict: string | null;
  result: ExecutionResult | null;
  created_at: string;
  finished_at: string | null;
};

export type SystemStatus = {
  execution: { enabled: boolean; backend: string; sandbox_ready: boolean };
  llm: { provider: string };
  features: Record<string, boolean>;
  content: { allow_unreviewed: boolean };
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function getApiHealth(fetcher: typeof fetch = fetch): Promise<HealthResponse> {
  const response = await fetcher(`${API_URL}/health`, { cache: "no-store" });
  if (!response.ok) {
    const fallback: ApiError = { code: "api_unavailable", message: "The API is unavailable.", request_id: response.headers.get("x-request-id") ?? "unknown" };
    throw fallback;
  }
  return response.json() as Promise<HealthResponse>;
}

async function parseError(response: Response): Promise<ApiRequestError> {
  const requestId = response.headers.get("x-request-id") ?? "unknown";
  try {
    const body = (await response.json()) as { error?: ApiError; detail?: unknown };
    if (body.error) return new ApiRequestError(response.status, body.error);
    if (body.detail && typeof body.detail === "object" && "message" in body.detail) {
      const detail = body.detail as { code?: string; message: string };
      return new ApiRequestError(response.status, { code: detail.code ?? "request_failed", message: detail.message, request_id: requestId });
    }
  } catch {
    // Fall through to a generic message; the body was not JSON.
  }
  return new ApiRequestError(response.status, {
    code: "request_failed",
    message: `Reps API request failed (${response.status}). Is the local API running and seeded?`,
    request_id: requestId,
  });
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
  } catch {
    throw new ApiRequestError(0, { code: "api_unreachable", message: "Cannot reach the Reps API. Start it with `make dev`.", request_id: "none" });
  }
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

export function newKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID().replaceAll("-", "");
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
}

export function listProblems(): Promise<ProblemSummary[]> {
  return apiRequest<ProblemSummary[]>("/v1/problems");
}

export function getProblem(slug: string): Promise<ProblemDetail> {
  return apiRequest<ProblemDetail>(`/v1/problems/${encodeURIComponent(slug)}`);
}

export function exportLocalData(): Promise<Record<string, unknown>> {
  return apiRequest<Record<string, unknown>>("/v1/me/export");
}

export function resetLocalHistory(): Promise<{ status: "reset"; deleted: Record<string, number> }> {
  return apiRequest("/v1/me/history", { method: "DELETE" });
}

export function getSystemStatus(): Promise<SystemStatus> {
  return apiRequest<SystemStatus>("/v1/system/status");
}

export function createExecution(body: { problem_slug: string; code: string; kind: "run" | "submit"; idempotency_key: string; session_id?: string }): Promise<Execution> {
  return apiRequest<Execution>("/v1/executions", { method: "POST", body: JSON.stringify(body) });
}

export function getExecution(id: string): Promise<Execution> {
  return apiRequest<Execution>(`/v1/executions/${encodeURIComponent(id)}`);
}

// --- Interviews (M4/M9) ---------------------------------------------------------------

export type InterviewState = "INTRO" | "CLARIFICATION" | "APPROACH_DISCUSSION" | "IMPLEMENTATION" | "TESTING" | "COMPLEXITY" | "FOLLOW_UP" | "COMPLETE" | "ABANDONED";

export type TranscriptEvent = {
  sequence: number;
  type: string;
  actor: "learner" | "interviewer" | "system";
  occurred_at: string;
  payload: Record<string, unknown> & { content?: string };
};

export type InterviewView = {
  id: string;
  problem_slug: string;
  mode: "practice" | "mock";
  state: InterviewState;
  version: number;
  result: string | null;
  started_at: string;
  completed_at: string | null;
  server_now: string;
  deadline_at: string | null;
  time_limit_s: number | null;
  accommodations: { time_multiplier?: number; reduce_motion?: boolean };
  policy: { mode: string; version: string; hint_budget: number; max_hint_level: number; clarification_style: string; idle_checkin_s: number | null };
  hints_used: number;
  max_hint_level: number;
  current_code: string | null;
  allowed_transitions: InterviewState[];
  solution_viewed: boolean;
  evaluation: { id: string; status: string } | null;
  transcript: TranscriptEvent[];
};

export type InterviewSummary = {
  id: string;
  problem_slug: string;
  problem_title: string;
  mode: "practice" | "mock";
  state: InterviewState;
  result: string | null;
  started_at: string;
  completed_at: string | null;
  hints_used: number;
  evaluation_id: string | null;
};

export function startInterview(body: { problem_slug: string; mode: "practice" | "mock"; time_multiplier?: number; reduce_motion?: boolean }): Promise<InterviewView> {
  return apiRequest("/v1/interviews", { method: "POST", body: JSON.stringify(body) });
}

export function listInterviews(): Promise<InterviewSummary[]> {
  return apiRequest("/v1/interviews");
}

export function getInterview(id: string): Promise<InterviewView> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(id)}`);
}

export function sendInterviewMessage(id: string, content: string, expectedVersion: number): Promise<InterviewView> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(id)}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, expected_version: expectedVersion, idempotency_key: newKey(), client_timestamp: new Date().toISOString() }),
  });
}

export function saveInterviewCode(id: string, code: string): Promise<{ version: number; saved: boolean }> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(id)}/code`, { method: "PUT", body: JSON.stringify({ code, idempotency_key: newKey() }) });
}

export function advanceInterview(id: string, target: InterviewState, expectedVersion: number): Promise<InterviewView> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(id)}/advance`, {
    method: "POST",
    body: JSON.stringify({ target, expected_version: expectedVersion, idempotency_key: newKey() }),
  });
}

export function requestInterviewHint(id: string, expectedVersion: number): Promise<InterviewView> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(id)}/hints`, {
    method: "POST",
    body: JSON.stringify({ expected_version: expectedVersion, idempotency_key: newKey() }),
  });
}

export function reportIdle(id: string, expectedVersion: number, idleSeconds: number): Promise<InterviewView> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(id)}/idle`, {
    method: "POST",
    body: JSON.stringify({ expected_version: expectedVersion, idle_seconds: idleSeconds }),
  });
}

// --- Reports (M5) ---------------------------------------------------------------------

export type Weakness = { capability: string; severity: "low" | "medium" | "high"; explanation: string; evidence_event_ids: string[]; confidence: number; source: "facts" | "rules" | "llm" };
export type Claim = { text: string; evidence_event_ids: string[] };
export type ScoreDimension = { score: number; explanation: string };

export type InterviewReport = {
  evaluation_id: string;
  session_id: string;
  status: "completed" | "degraded" | "failed";
  evaluator: string;
  provider: string;
  model: string;
  prompt_version: string;
  schema_version: number;
  created_at: string;
  capability_names: Record<string, string>;
  evidence: Record<string, { sequence: number; type: string; actor: string; excerpt: string }>;
  flags: Array<{ capability_slug: string | null; reason: string; status: string }>;
  scheduled: Array<{ task_type: string; label: string; capability: string; due_at: string; status: string }>;
  report: {
    problem_slug: string;
    facts: Record<string, unknown> & {
      result: string;
      passed_hidden: boolean;
      best_hidden_passed: number;
      hidden_total: number;
      runs: number;
      submissions: number;
      hints_used: number;
      max_hint_level: number;
      solution_viewed: boolean;
      duration_s: number;
      mode: "practice" | "mock";
      complexity_time_correct: boolean | null;
      complexity_space_correct: boolean | null;
    };
    strengths: Claim[];
    weaknesses: Weakness[];
    misconceptions: Claim[];
    communication: { rating: number; summary: string };
    reasoning: { rating: number; summary: string };
    confidence: number;
    transfer_confidence: "low" | "medium" | "high";
    scorecard: null | { rubric_version: string; correctness: ScoreDimension; reasoning: ScoreDimension; communication: ScoreDimension; complexity: ScoreDimension; independence: ScoreDimension };
    interpretation_source: "llm" | "rules";
    notes: string[];
  };
};

export function getReport(sessionId: string): Promise<InterviewReport> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(sessionId)}/report`);
}

export function retryReport(sessionId: string): Promise<InterviewReport> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(sessionId)}/report/retry`, { method: "POST" });
}

export function flagReport(sessionId: string, body: { capability_slug?: string | null; reason: string }): Promise<InterviewReport> {
  return apiRequest(`/v1/interviews/${encodeURIComponent(sessionId)}/report/flags`, { method: "POST", body: JSON.stringify(body) });
}

// --- Reviews, drills, learner (M6-M8) -------------------------------------------------

export type ReviewTaskView = {
  id: string;
  task_type: string;
  label: string;
  status: string;
  due_at: string;
  reason: string;
  capability: { slug: string; name: string };
  estimated_minutes: number;
  problem_slug: string | null;
  problem_title: string | null;
  source_type: string;
  step: number;
  attempt_count: number;
};

export type ReviewFeedback = {
  correctness: number;
  band: "correct" | "partial" | "missed";
  feedback: string;
  missing_points: string[];
  misconceptions: string[];
  recommended_action: "advance" | "review" | "coach" | "rebuild";
  reference_answer: string | null;
  grader: string;
  rebuild: null | { misconception: string; explanation: string; confirmation_question: string | null };
  confirmation?: { answer: string; correctness: number; feedback: string };
};

export type ReviewItem = {
  attempt_id: string;
  task: ReviewTaskView | null;
  task_type: string;
  mode: "retrieve" | "coach" | "rebuild";
  status: "in_progress" | "submitted";
  prompt: string;
  kind: "text" | "code" | "interview";
  problem_slug: string | null;
  starter_code: string | null;
  hints_used: number;
  hints_total: number;
  hints: string[];
  result: ReviewFeedback | null;
  interview_session_id: string | null;
};

export function getReviewQueue(): Promise<{ due: ReviewTaskView[]; upcoming: ReviewTaskView[]; server_now: string }> {
  return apiRequest("/v1/reviews/queue");
}

export function getReviewHistory(): Promise<Array<{ attempt_id: string; completed_at: string | null; task_type: string | null; capability: string | null; capability_slug: string | null; band: string | null; hints_used: number }>> {
  return apiRequest("/v1/reviews/history");
}

export function startReview(taskId: string, drillSessionId?: string): Promise<ReviewItem> {
  return apiRequest(`/v1/reviews/tasks/${encodeURIComponent(taskId)}/start`, { method: "POST", body: JSON.stringify({ drill_session_id: drillSessionId ?? null }) });
}

export function getReviewAttempt(attemptId: string): Promise<ReviewItem> {
  return apiRequest(`/v1/reviews/attempts/${encodeURIComponent(attemptId)}`);
}

export function reviewHint(attemptId: string): Promise<ReviewItem> {
  return apiRequest(`/v1/reviews/attempts/${encodeURIComponent(attemptId)}/hint`, { method: "POST" });
}

export function answerReview(attemptId: string, body: { answer?: string; job_id?: string; confidence?: number }): Promise<ReviewItem> {
  return apiRequest(`/v1/reviews/attempts/${encodeURIComponent(attemptId)}/answer`, { method: "POST", body: JSON.stringify(body) });
}

export function confirmReview(attemptId: string, answer: string): Promise<ReviewItem> {
  return apiRequest(`/v1/reviews/attempts/${encodeURIComponent(attemptId)}/confirm`, { method: "POST", body: JSON.stringify({ answer }) });
}

export function snoozeTask(taskId: string, days: number): Promise<ReviewTaskView> {
  return apiRequest(`/v1/reviews/tasks/${encodeURIComponent(taskId)}/snooze`, { method: "POST", body: JSON.stringify({ days }) });
}

export function skipTask(taskId: string): Promise<ReviewTaskView> {
  return apiRequest(`/v1/reviews/tasks/${encodeURIComponent(taskId)}/skip`, { method: "POST" });
}

export function reportTask(taskId: string, reason: string): Promise<ReviewTaskView> {
  return apiRequest(`/v1/reviews/tasks/${encodeURIComponent(taskId)}/report`, { method: "POST", body: JSON.stringify({ reason }) });
}

export type DrillItem = { index: number; task_id: string; kind: "task" | "practice"; task_type: string; capability_slug: string; topic: string; minutes: number; reason: string; status: "pending" | "in_progress" | "done" | "skipped"; band: string | null; task: ReviewTaskView | null };
export type Drill = { id: string; status: "active" | "paused" | "completed" | "abandoned"; budget_minutes: number; planned_minutes: number; mix: string; items: DrillItem[]; completed_items: number; current_index: number | null; started_at: string; completed_at: string | null };

export function createDrill(budgetMinutes: number): Promise<Drill> {
  return apiRequest("/v1/drills", { method: "POST", body: JSON.stringify({ budget_minutes: budgetMinutes }) });
}

export function getActiveDrill(): Promise<Drill | null> {
  return apiRequest("/v1/drills/active");
}

export function getDrill(id: string): Promise<Drill> {
  return apiRequest(`/v1/drills/${encodeURIComponent(id)}`);
}

export function drillAction(id: string, action: "pause" | "resume" | "complete" | "abandon"): Promise<Drill> {
  return apiRequest(`/v1/drills/${encodeURIComponent(id)}/actions`, { method: "POST", body: JSON.stringify({ action }) });
}

export type Band = "Weak" | "Developing" | "Reliable" | "Strong";
export type CapabilityStateView = { slug: string; name: string; type: string; topic: { slug: string; name: string }; band: Band; explanation: string; evidence_count: number; confidence: "low" | "medium" | "high"; last_reviewed_at: string | null; next_review_at: string | null };
export type EvidenceView = { id: string; occurred_at: string; source_type: string; source_id: string; exercise_type: string; problem_title: string | null; outcome: "success" | "partial" | "miss"; hint_level: number; assisted: boolean; transfer: boolean; repeat_exposure: boolean; excluded: boolean; explanation: string };
export type Dashboard = {
  due_count: number;
  due: ReviewTaskView[];
  upcoming: ReviewTaskView[];
  weak_capabilities: CapabilityStateView[];
  patterns: Array<{ slug: string; name: string; band: Band; bands: Record<string, number> }>;
  recent_interviews: Array<{ id: string; problem_title: string; mode: string; state: string; result: string | null; started_at: string }>;
  reviews_completed: number;
};

export function getDashboard(): Promise<Dashboard> {
  return apiRequest("/v1/learner/dashboard");
}

export function getCapabilities(topic?: string): Promise<CapabilityStateView[]> {
  return apiRequest(`/v1/learner/capabilities${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`);
}

export function getCapabilityEvidence(slug: string, filters: { source_type?: string; days?: number } = {}): Promise<EvidenceView[]> {
  const params = new URLSearchParams();
  if (filters.source_type) params.set("source_type", filters.source_type);
  if (filters.days) params.set("days", String(filters.days));
  const query = params.toString();
  return apiRequest(`/v1/learner/capabilities/${encodeURIComponent(slug)}/evidence${query ? `?${query}` : ""}`);
}

export function rebuildLearnerState(): Promise<{ capabilities: number }> {
  return apiRequest("/v1/learner/rebuild", { method: "POST" });
}

// --- Solutions (M10) and settings -----------------------------------------------------

export type SolutionReveal = { problem_slug: string; reference_solution: string; key_insight: string; time_complexity: string; space_complexity: string; scheduled: Array<{ task_type: string; due_at: string; reason: string }>; notice: string };

export function viewSolution(slug: string, sessionId?: string): Promise<SolutionReveal> {
  return apiRequest(`/v1/problems/${encodeURIComponent(slug)}/solution`, { method: "POST", body: JSON.stringify({ confirm: true, session_id: sessionId ?? null }) });
}

export function getProblemProgress(slug: string): Promise<{ solution_viewed: boolean; stages: Array<{ stage: string; label: string; status: "done" | "scheduled" | "not_scheduled" }> }> {
  return apiRequest(`/v1/problems/${encodeURIComponent(slug)}/progress`);
}

export type LearnerSettings = { timezone: string; daily_review_cap: number; mock_time_multiplier: number; reduce_timer_motion: boolean };

export function getSettings(): Promise<LearnerSettings> {
  return apiRequest("/v1/settings");
}

export function updateSettings(body: Partial<LearnerSettings>): Promise<LearnerSettings> {
  return apiRequest("/v1/settings", { method: "PATCH", body: JSON.stringify(body) });
}

// --- AI provider settings -------------------------------------------------------------

export type LLMProviderName = "openai" | "gemini";
export type LLMChoice = "env" | "offline" | LLMProviderName;
export type LLMSettings = {
  active: LLMChoice;
  effective: string;
  env_provider: string;
  providers: Record<LLMProviderName, { has_key: boolean; key_hint: string | null; model: string; env_key_present: boolean }>;
  storage_note: string;
};

export function getLLMSettings(): Promise<LLMSettings> {
  return apiRequest("/v1/settings/llm");
}

export function updateLLMSettings(body: {
  active?: LLMChoice;
  openai?: { api_key?: string; clear_key?: boolean; model?: string };
  gemini?: { api_key?: string; clear_key?: boolean; model?: string };
}): Promise<LLMSettings> {
  return apiRequest("/v1/settings/llm", { method: "PUT", body: JSON.stringify(body) });
}

export function listLLMModels(provider: LLMProviderName): Promise<{ provider: string; models: string[] }> {
  return apiRequest(`/v1/settings/llm/${provider}/models`);
}

export function testLLM(provider: LLMProviderName): Promise<{ ok: boolean; model: string; latency_ms?: number; error_code: string | null; message: string }> {
  return apiRequest("/v1/settings/llm/test", { method: "POST", body: JSON.stringify({ provider }) });
}
