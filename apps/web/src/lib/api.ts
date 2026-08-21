export type ApiError = { code: string; message: string; request_id: string };

export type HealthResponse = {
  status: "ok" | "degraded";
  service: string;
  version: string;
  request_id: string;
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
