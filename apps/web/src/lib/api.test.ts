import { describe, expect, it, vi } from "vitest";
import { getApiHealth } from "./api";

describe("getApiHealth", () => {
  it("returns a typed health response", async () => {
    const payload = { status: "ok", service: "reps-api", version: "0.1.0", request_id: "req-1" } as const;
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    await expect(getApiHealth(fetcher)).resolves.toEqual(payload);
  });

  it("normalizes an unavailable API", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 503, headers: { "x-request-id": "req-2" } }));
    await expect(getApiHealth(fetcher)).rejects.toEqual({ code: "api_unavailable", message: "The API is unavailable.", request_id: "req-2" });
  });
});
