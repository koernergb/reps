"use client";

import { Eye } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { errorMessage, viewSolution, type SolutionReveal } from "@/lib/api";

const STAGE_LABEL: Record<string, string> = {
  key_insight: "Now: explain the key insight without looking",
  pseudocode: "Tomorrow: reconstruct it in pseudocode",
  implementation: "In a few days: implement it from memory",
  transfer: "In about 10 days: a related problem",
  reinterview: "In about 3 weeks: an unseen transfer interview",
};

export function SolutionReveal({ slug, sessionId, onViewed }: { slug: string; sessionId?: string; onViewed?: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [solution, setSolution] = useState<SolutionReveal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function reveal() {
    setBusy(true);
    try {
      setSolution(await viewSolution(slug, sessionId));
      setConfirming(false);
      onViewed?.();
    } catch (reason) {
      setError(errorMessage(reason, "Could not load the solution."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button onClick={() => setConfirming(true)} variant="ghost"><Eye aria-hidden className="mr-1.5" size={15} /> View solution</Button>
      <ConfirmDialog busy={busy} confirmLabel="Show the solution" onCancel={() => setConfirming(false)} onConfirm={reveal} open={confirming} title="View the reference solution?">
        <p>Viewing the solution changes your learning plan. This problem will count as <strong>assisted</strong>: solving it later won&apos;t count as independent, and Reps will schedule a comprehension check now, a reconstruction tomorrow, an implementation in a few days, and related problems after that.</p>
      </ConfirmDialog>
      {error ? <p className="mt-2 text-sm text-red-800" role="alert">{error}</p> : null}
      {solution ? (
        <section aria-label="Reference solution" className="fixed inset-x-4 bottom-4 z-40 max-h-[70vh] overflow-auto rounded-2xl border bg-white p-5 shadow-2xl sm:left-auto sm:w-[36rem]">
          <div className="flex items-start justify-between gap-4">
            <h2 className="font-bold">Reference solution</h2>
            <Button onClick={() => setSolution(null)} variant="ghost">Close</Button>
          </div>
          <p className="mt-2 text-sm"><strong>Key insight:</strong> {solution.key_insight}</p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs leading-5 text-slate-100"><code>{solution.reference_solution}</code></pre>
          <p className="mt-2 text-xs text-[var(--muted)]">Time {solution.time_complexity} · Space {solution.space_complexity}</p>
          <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">{solution.notice}</p>
          {solution.scheduled.length ? (
            <ul className="mt-3 space-y-1 text-sm">
              {solution.scheduled.map((item) => <li key={item.task_type}>• {STAGE_LABEL[item.task_type] ?? item.task_type}</li>)}
            </ul>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
