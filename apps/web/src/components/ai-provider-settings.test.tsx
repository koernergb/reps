import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AIProviderSettings } from "./ai-provider-settings";

const base = {
  active: "env",
  effective: "offline",
  env_provider: "offline",
  providers: {
    openai: { has_key: false, key_hint: null, model: "gpt-4.1-mini", env_key_present: false },
    gemini: { has_key: false, key_hint: null, model: "gemini-2.5-flash", env_key_present: false },
  },
  storage_note: "Keys are stored locally.",
};

afterEach(() => vi.unstubAllGlobals());

describe("AIProviderSettings", () => {
  it("disables providers without keys and saves a key without echoing it", async () => {
    const saved = { ...base, providers: { ...base.providers, gemini: { ...base.providers.gemini, has_key: true, key_hint: "…wxyz" } } };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(base), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(saved), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AIProviderSettings />);
    await screen.findByText("AI provider");
    expect(screen.getByRole("radio", { name: /Google Gemini/ })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Gemini API key"), { target: { value: "AIza-secret-wxyz" } });
    fireEvent.click(screen.getAllByRole("button", { name: /Save key/ })[1]);
    await waitFor(() => expect(screen.getByText("Key saved (…wxyz)")).toBeInTheDocument());
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string)).toEqual({ gemini: { api_key: "AIza-secret-wxyz", model: "gemini-2.5-flash" } });
    expect(screen.getByLabelText("Gemini API key")).toHaveValue("");
    expect(screen.getByRole("radio", { name: /Google Gemini/ })).toBeEnabled();
  });
});
