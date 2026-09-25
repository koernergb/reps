"use client";

import { CheckCircle2, KeyRound, ListRestart, LoaderCircle, PlugZap, Trash2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { errorMessage, getLLMSettings, listLLMModels, testLLM, updateLLMSettings, type LLMChoice, type LLMProviderName, type LLMSettings } from "@/lib/api";
import { cn } from "@/lib/cn";

const PROVIDERS: Record<LLMProviderName, { label: string; keyUrl: string; keyLabel: string }> = {
  openai: { label: "OpenAI", keyUrl: "https://platform.openai.com/api-keys", keyLabel: "OpenAI API key" },
  gemini: { label: "Google Gemini", keyUrl: "https://aistudio.google.com/apikey", keyLabel: "Gemini API key" },
};

type TestResult = Awaited<ReturnType<typeof testLLM>>;

function ProviderPanel({ name, settings, onChange }: { name: LLMProviderName; settings: LLMSettings; onChange: (next: LLMSettings) => void }) {
  const info = PROVIDERS[name];
  const state = settings.providers[name];
  const [key, setKey] = useState("");
  const [model, setModel] = useState(state.model);
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [test, setTest] = useState<TestResult | null>(null);

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setMessage(null);
    try {
      await action();
    } catch (error) {
      setMessage(errorMessage(error, "That didn't work."));
    } finally {
      setBusy(null);
    }
  }

  const saveKey = () => run("key", async () => {
    onChange(await updateLLMSettings({ [name]: { api_key: key, model } }));
    setKey("");
    setTest(null);
    setMessage("Key saved.");
  });
  const removeKey = () => run("remove", async () => {
    const next = await updateLLMSettings({ [name]: { clear_key: true }, ...(settings.active === name ? { active: "env" as LLMChoice } : {}) });
    onChange(next);
    setTest(null);
    setMessage("Key removed.");
  });
  const saveModel = () => run("model", async () => {
    onChange(await updateLLMSettings({ [name]: { model } }));
    setTest(null);
    setMessage("Model saved.");
  });
  const loadModels = () => run("models", async () => {
    const result = await listLLMModels(name);
    setModels(result.models);
    setMessage(`${result.models.length} models available.`);
  });
  const runTest = () => run("test", async () => setTest(await testLLM(name)));

  const inputId = `${name}-key`;
  const modelId = `${name}-model`;
  return (
    <div className="rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">{info.label}</h3>
        <span className="text-xs text-[var(--muted)]">{state.has_key ? `Key saved (${state.key_hint})` : state.env_key_present ? "Key from .env" : "No key"}</span>
      </div>
      <label className="mt-3 block text-sm font-semibold" htmlFor={inputId}>{info.keyLabel}</label>
      <div className="mt-1 flex flex-wrap gap-2">
        <input autoComplete="off" className="min-w-0 flex-1 rounded-lg border px-3 py-2 font-mono text-sm" id={inputId} onChange={(event) => setKey(event.target.value)} placeholder={state.has_key ? "Enter a new key to replace the saved one" : "Paste your key"} spellCheck={false} type="password" value={key} />
        <Button disabled={!key.trim() || busy !== null} onClick={saveKey}><KeyRound aria-hidden className="mr-1.5" size={15} /> Save key</Button>
        {state.has_key ? <Button disabled={busy !== null} onClick={removeKey} variant="ghost"><Trash2 aria-hidden className="mr-1.5" size={15} /> Remove</Button> : null}
      </div>
      <p className="mt-1 text-xs text-[var(--muted)]">Get a key at <a className="underline" href={info.keyUrl} rel="noreferrer" target="_blank">{info.keyUrl.replace("https://", "")}</a>.</p>
      <label className="mt-4 block text-sm font-semibold" htmlFor={modelId}>Model</label>
      <div className="mt-1 flex flex-wrap gap-2">
        <input className="min-w-0 flex-1 rounded-lg border px-3 py-2 font-mono text-sm" id={modelId} list={`${modelId}-options`} onChange={(event) => setModel(event.target.value)} value={model} />
        <datalist id={`${modelId}-options`}>{models.map((item) => <option key={item} value={item} />)}</datalist>
        <Button disabled={busy !== null || !model.trim() || model === state.model} onClick={saveModel} variant="secondary">Save model</Button>
        <Button disabled={busy !== null || !state.has_key} onClick={loadModels} variant="ghost"><ListRestart aria-hidden className="mr-1.5" size={15} /> Load models</Button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled={busy !== null || !state.has_key} onClick={runTest} variant="secondary">
          {busy === "test" ? <LoaderCircle aria-hidden className="mr-1.5 animate-spin" size={15} /> : <PlugZap aria-hidden className="mr-1.5" size={15} />} Test connection
        </Button>
        {test ? (
          <p className={cn("flex items-center gap-1.5 text-sm", test.ok ? "text-green-800" : "text-red-800")} role="status">
            {test.ok ? <CheckCircle2 aria-hidden size={15} /> : <XCircle aria-hidden size={15} />}
            {test.ok ? `Works with ${test.model} (${test.latency_ms} ms).` : `${test.error_code}: ${test.message}`}
          </p>
        ) : null}
      </div>
      {message ? <p className="mt-2 text-sm text-[var(--muted)]" role="status">{message}</p> : null}
    </div>
  );
}

export function AIProviderSettings() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLLMSettings().then(setSettings).catch((reason: unknown) => setError(errorMessage(reason, "Could not load AI settings.")));
  }, []);

  async function choose(active: LLMChoice) {
    setError(null);
    try {
      setSettings(await updateLLMSettings({ active }));
    } catch (reason) {
      setError(errorMessage(reason, "Could not change the provider."));
    }
  }

  if (!settings) return error ? <p className="mt-5 text-sm text-red-800" role="alert">{error}</p> : null;
  const options: Array<{ value: LLMChoice; label: string; detail: string; disabled?: boolean }> = [
    { value: "offline", label: "Offline", detail: "Built-in rule-based interviewer and grader. Nothing leaves your machine." },
    { value: "openai", label: "OpenAI", detail: settings.providers.openai.has_key ? settings.providers.openai.model : "Add a key below first", disabled: !settings.providers.openai.has_key },
    { value: "gemini", label: "Google Gemini", detail: settings.providers.gemini.has_key ? settings.providers.gemini.model : "Add a key below first", disabled: !settings.providers.gemini.has_key },
    { value: "env", label: "Use .env", detail: `Follow LLM_PROVIDER in .env (currently ${settings.env_provider}).` },
  ];
  return (
    <section className="mt-5 rounded-2xl border bg-white p-6 sm:p-8">
      <h2 className="text-xl font-bold">AI provider</h2>
      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Powers the interviewer, answer grading, and report interpretation. Test results and hints never depend on it. Currently using <strong>{settings.effective}</strong>.</p>
      <fieldset className="mt-5">
        <legend className="sr-only">Active AI provider</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {options.map((option) => (
            <label className={cn("flex cursor-pointer gap-3 rounded-xl border p-3 text-sm has-[:checked]:border-green-700 has-[:checked]:ring-1 has-[:checked]:ring-green-700", option.disabled && "cursor-not-allowed opacity-50")} key={option.value}>
              <input checked={settings.active === option.value} className="mt-0.5 accent-green-700" disabled={option.disabled} name="llm-provider" onChange={() => void choose(option.value)} type="radio" />
              <span><span className="font-semibold">{option.label}</span><span className="block text-xs text-[var(--muted)]">{option.detail}</span></span>
            </label>
          ))}
        </div>
      </fieldset>
      {error ? <p className="mt-3 text-sm text-red-800" role="alert">{error}</p> : null}
      <div className="mt-6 grid gap-4">
        {(Object.keys(PROVIDERS) as LLMProviderName[]).map((name) => <ProviderPanel key={name} name={name} onChange={setSettings} settings={settings} />)}
      </div>
      <p className="mt-4 text-xs leading-5 text-[var(--muted)]">{settings.storage_note} When a provider is active, interview content is sent to it as described on the <a className="underline" href="/privacy">privacy page</a>.</p>
    </section>
  );
}
