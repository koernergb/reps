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
