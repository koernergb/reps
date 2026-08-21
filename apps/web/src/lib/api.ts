export type ApiError = { code: string; message: string; request_id: string };

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
  capabilities: CapabilitySummary[];
};

export type ProblemDetail = ProblemSummary & {
  statement: string;
  examples: Array<{ input: Record<string, unknown>; output: unknown }>;
  constraints: string[];
  starter_code: string;
  visible_tests: Array<{ args: unknown[]; expected: unknown }>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getApiHealth(fetcher: typeof fetch = fetch): Promise<HealthResponse> {
  const response = await fetcher(`${API_URL}/health`, { cache: "no-store" });
  if (!response.ok) {
    const fallback: ApiError = { code: "api_unavailable", message: "The API is unavailable.", request_id: response.headers.get("x-request-id") ?? "unknown" };
    throw fallback;
  }
  return response.json() as Promise<HealthResponse>;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    throw new Error(`Reps API request failed (${response.status}). Is the local API running and seeded?`);
  }
  return response.json() as Promise<T>;
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
