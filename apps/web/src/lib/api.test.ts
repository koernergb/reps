import { describe, expect, it, vi } from "vitest";
import { getApiHealth, getProblem, listProblems, resetLocalHistory } from "./api";

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

describe("local product API", () => {
  it("lists problems without adding client ownership fields", async () => {
    const payload = [{ id: "1", slug: "pair", title: "Pair", difficulty: "easy", language: "python", status: "development", capabilities: [] }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 })));
    await expect(listProblems()).resolves.toEqual(payload);
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/v1/problems", expect.objectContaining({ cache: "no-store" }));
    vi.unstubAllGlobals();
  });

  it("encodes a problem slug", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ slug: "a/b" }), { status: 200 })));
    await getProblem("a/b");
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/v1/problems/a%2Fb", expect.any(Object));
    vi.unstubAllGlobals();
  });

  it("uses DELETE for a confirmed history reset", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "reset", deleted: {} }), { status: 200 })));
    await resetLocalHistory();
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/v1/me/history", expect.objectContaining({ method: "DELETE" }));
    vi.unstubAllGlobals();
  });
});
