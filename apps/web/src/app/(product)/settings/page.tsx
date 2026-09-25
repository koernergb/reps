"use client";

import { Download, RefreshCcw, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { AIProviderSettings } from "@/components/ai-provider-settings";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { errorMessage, exportLocalData, getSettings, rebuildLearnerState, resetLocalHistory, updateSettings, type LearnerSettings } from "@/lib/api";

const ZONES = typeof Intl !== "undefined" && "supportedValuesOf" in Intl ? (Intl as unknown as { supportedValuesOf: (key: string) => string[] }).supportedValuesOf("timeZone") : ["UTC"];

export default function SettingsPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<LearnerSettings | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    getSettings().then(setSettings).catch((reason: unknown) => setMessage(errorMessage(reason, "Could not load settings.")));
  }, []);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setMessage(null);
    try {
      setMessage(await action());
    } catch (error) {
      setMessage(errorMessage(error, "That didn't work."));
    } finally {
      setBusy(false);
    }
  }

  const download = () => run(async () => {
    const data = await exportLocalData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `reps-local-export-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    return "Local data export created.";
  });

  return (
    <div className="mx-auto max-w-3xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Local data</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Settings and privacy</h1>
      {settings ? (
        <section className="mt-10 rounded-2xl border bg-white p-6 sm:p-8">
          <h2 className="text-xl font-bold">Schedule and accommodations</h2>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <label className="text-sm font-semibold">Time zone
              <select className="mt-1 block w-full rounded-lg border px-3 py-2 font-normal" onChange={(event) => setSettings({ ...settings, timezone: event.target.value })} value={settings.timezone}>
                {[settings.timezone, ...ZONES.filter((zone) => zone !== settings.timezone)].map((zone) => <option key={zone} value={zone}>{zone}</option>)}
              </select>
              <span className="mt-1 block text-xs font-normal text-[var(--muted)]">Reviews become due at 4 a.m. local time.</span>
            </label>
            <label className="text-sm font-semibold">Daily review cap
              <input className="mt-1 block w-full rounded-lg border px-3 py-2 font-normal" max={50} min={1} onChange={(event) => setSettings({ ...settings, daily_review_cap: Number(event.target.value) })} type="number" value={settings.daily_review_cap} />
              <span className="mt-1 block text-xs font-normal text-[var(--muted)]">Extra reviews move to the next day.</span>
            </label>
            <label className="text-sm font-semibold">Mock interview extra time
              <select className="mt-1 block w-full rounded-lg border px-3 py-2 font-normal" onChange={(event) => setSettings({ ...settings, mock_time_multiplier: Number(event.target.value) })} value={settings.mock_time_multiplier}>
                {[1, 1.25, 1.5, 2].map((value) => <option key={value} value={value}>{value === 1 ? "Standard (45 min)" : `${value}× (${Math.round(45 * value)} min)`}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 self-center text-sm font-semibold">
              <input checked={settings.reduce_timer_motion} className="size-4 accent-green-700" onChange={(event) => setSettings({ ...settings, reduce_timer_motion: event.target.checked })} type="checkbox" />
              Calm timer (no ticking seconds)
            </label>
          </div>
          <Button className="mt-6" disabled={busy} onClick={() => run(async () => { setSettings(await updateSettings(settings)); return "Settings saved."; })}><Save aria-hidden className="mr-2" size={16} /> Save</Button>
        </section>
      ) : null}
      <AIProviderSettings />
      <section className="mt-5 rounded-2xl border bg-white p-6 sm:p-8">
        <h2 className="text-xl font-bold">Export</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Download everything Reps stores about your learning: attempts, capability evidence and state, interviews and events, submitted code, reports, reviews, drills, hints, and analytics. Hidden tests and reference solutions are never included.</p>
        <Button className="mt-5" disabled={busy} onClick={download} variant="secondary"><Download aria-hidden className="mr-2" size={17} /> Export local data</Button>
      </section>
      <section className="mt-5 rounded-2xl border bg-white p-6 sm:p-8">
        <h2 className="text-xl font-bold">Rebuild skill estimates</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Recompute every skill band from stored evidence. Use this after reporting inaccurate diagnoses; results are deterministic.</p>
        <Button className="mt-5" disabled={busy} onClick={() => run(async () => `Rebuilt ${(await rebuildLearnerState()).capabilities} skill estimates.`)} variant="secondary"><RefreshCcw aria-hidden className="mr-2" size={17} /> Rebuild</Button>
      </section>
      <section className="mt-5 rounded-2xl border border-red-200 bg-white p-6 sm:p-8">
        <h2 className="text-xl font-bold">Reset learning history</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Permanently removes all learner-owned records listed above. The local profile and problem corpus remain.</p>
        <Button className="mt-5 border-red-300 text-red-800 hover:bg-red-50" disabled={busy} onClick={() => setConfirmReset(true)} variant="secondary"><RotateCcw aria-hidden className="mr-2" size={17} /> Reset history</Button>
      </section>
      <ConfirmDialog confirmLabel="Delete my history" destructive onCancel={() => setConfirmReset(false)} onConfirm={() => { setConfirmReset(false); void run(async () => { const result = await resetLocalHistory(); return `Local learning history reset. ${Object.values(result.deleted).reduce((sum, value) => sum + value, 0)} records deleted.`; }); }} open={confirmReset} title="Delete all learning history?">
        <p>This permanently deletes interviews, code, reports, reviews, drills, evidence, and skill estimates. It cannot be undone. Consider exporting first.</p>
      </ConfirmDialog>
      {message ? <p className="mt-5 rounded-xl bg-stone-100 px-4 py-3 text-sm" role="status">{message}</p> : null}
    </div>
  );
}
