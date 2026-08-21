"use client";

import { Download, RotateCcw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { exportLocalData, resetLocalHistory } from "@/lib/api";

export default function SettingsPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function downloadExport() {
    setBusy(true);
    setMessage(null);
    try {
      const data = await exportLocalData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `reps-local-export-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("Local data export created.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resetHistory() {
    if (!window.confirm("Delete all local interview, review, hint, and learner-state history? Problem content remains.")) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await resetLocalHistory();
      const count = Object.values(result.deleted).reduce((sum, value) => sum + value, 0);
      setMessage(`Local learning history reset. ${count} records deleted.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Local data</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Settings and privacy</h1>
      <p className="mt-4 text-lg leading-8 text-[var(--muted)]">Reps stores its learning evidence in your local PostgreSQL database. No authentication protects a server exposed beyond this machine.</p>
      <section className="mt-10 rounded-2xl border bg-white p-6 sm:p-8"><h2 className="text-xl font-bold">Export</h2><p className="mt-2 text-sm leading-6 text-[var(--muted)]">Download your profile, attempts, capability state, interview sessions, events, and hint history as JSON. Corpus evaluator secrets are never included.</p><Button className="mt-5" disabled={busy} onClick={downloadExport} variant="secondary"><Download aria-hidden className="mr-2" size={17} /> Export local data</Button></section>
      <section className="mt-5 rounded-2xl border border-red-200 bg-white p-6 sm:p-8"><h2 className="text-xl font-bold">Reset learning history</h2><p className="mt-2 text-sm leading-6 text-[var(--muted)]">Permanently removes attempts, learner state, interviews, events, and hints. The local profile and problem corpus remain.</p><Button className="mt-5 border-red-300 text-red-800 hover:bg-red-50" disabled={busy} onClick={resetHistory} variant="secondary"><RotateCcw aria-hidden className="mr-2" size={17} /> Reset history</Button></section>
      {message ? <p className="mt-5 rounded-xl bg-stone-100 px-4 py-3 text-sm" role="status">{message}</p> : null}
    </div>
  );
}
