"use client";

import { CheckCircle2, Circle, LoaderCircle, Pause, Play, Target, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ReviewRunner } from "@/components/review/review-runner";
import { Button } from "@/components/ui/button";
import { createDrill, drillAction, errorMessage, getActiveDrill, getDrill, startReview, type Drill, type ReviewItem } from "@/lib/api";
import { cn } from "@/lib/cn";

const BUDGETS = [5, 10, 15];

export default function DrillsPage() {
  const [drill, setDrill] = useState<Drill | null>(null);
  const [item, setItem] = useState<ReviewItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getActiveDrill().then(setDrill).catch((reason: unknown) => setError(errorMessage(reason, "Could not load drills."))).finally(() => setLoading(false));
  }, []);

  const refresh = useCallback(async (id: string) => setDrill(await getDrill(id)), []);

  async function begin(budget: number) {
    setBusy(true);
    setError(null);
    try {
      setDrill(await createDrill(budget));
    } catch (reason) {
      setError(errorMessage(reason, "Could not start a drill."));
    } finally {
      setBusy(false);
    }
  }

  async function openItem(taskId: string) {
    if (!drill) return;
    setError(null);
    try {
      setItem(await startReview(taskId, drill.id));
    } catch (reason) {
      setError(errorMessage(reason, "Could not open this item."));
    }
  }

  async function act(action: "pause" | "resume" | "complete" | "abandon") {
    if (!drill) return;
    setBusy(true);
    try {
      const next = await drillAction(drill.id, action);
      setDrill(next.status === "abandoned" ? null : next);
      setItem(null);
    } catch (reason) {
      setError(errorMessage(reason, "That didn't work."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading…</p>;

  if (!drill || drill.status === "completed" && !item) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Daily practice</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight">Adaptive drill</h1>
        <p className="mt-3 text-[var(--muted)]">A short mix of your due reviews and your weakest skills, sized to your time budget.</p>
        {drill?.status === "completed" ? (
          <section className="mt-8 rounded-2xl border bg-green-50 p-6" role="status">
            <p className="flex items-center gap-2 font-bold text-green-950"><CheckCircle2 aria-hidden size={18} /> Drill complete: {drill.completed_items} of {drill.items.length} items</p>
            <p className="mt-2 text-sm text-green-950">{drill.items.filter((entry) => entry.band === "correct").length} correct, {drill.items.filter((entry) => entry.band === "partial").length} partly correct, {drill.items.filter((entry) => entry.band === "missed").length} to revisit. Missed items come back tomorrow.</p>
          </section>
        ) : null}
        {error ? <p className="mt-6 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {BUDGETS.map((budget) => (
            <button className="rounded-2xl border bg-white p-6 text-left hover:border-green-300 focus-visible:outline-2 focus-visible:outline-green-800 disabled:opacity-50" disabled={busy} key={budget} onClick={() => void begin(budget)} type="button">
              <Target aria-hidden className="text-green-800" />
              <p className="mt-4 text-2xl font-bold">{budget} min</p>
              <p className="text-sm text-[var(--muted)]">{budget === 10 ? "Recommended" : budget < 10 ? "Quick" : "Deeper"}</p>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">{drill.budget_minutes}-minute drill · planned {drill.planned_minutes} min</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">{drill.mix}</h1>
        </div>
        <div className="flex gap-2">
          {drill.status === "paused" ? <Button disabled={busy} onClick={() => void act("resume")} variant="secondary"><Play aria-hidden className="mr-1" size={15} /> Resume</Button> : <Button disabled={busy} onClick={() => void act("pause")} variant="secondary"><Pause aria-hidden className="mr-1" size={15} /> Pause</Button>}
          <Button disabled={busy} onClick={() => { if (window.confirm("Leave this drill? Completed items are kept.")) void act("abandon"); }} variant="ghost"><X aria-hidden className="mr-1" size={15} /> Exit</Button>
        </div>
      </div>
      {error ? <p className="mt-4 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
      <div className="mt-6 grid gap-6 lg:grid-cols-[18rem_1fr]">
        <ol aria-label="Drill items" className="space-y-2">
          {drill.items.map((entry) => (
            <li key={entry.task_id}>
              <button
                className={cn("flex w-full items-start gap-2 rounded-xl border bg-white p-3 text-left text-sm hover:border-green-300 focus-visible:outline-2 focus-visible:outline-green-800 disabled:opacity-60", item?.task?.id === entry.task_id && "border-green-700 ring-1 ring-green-700")}
                disabled={drill.status === "paused" || entry.status === "done" || entry.status === "skipped"}
                onClick={() => void openItem(entry.task_id)}
                type="button"
              >
                {entry.status === "done" ? <CheckCircle2 aria-label="Done" className="mt-0.5 shrink-0 text-green-700" size={16} /> : <Circle aria-label="Not done" className="mt-0.5 shrink-0 text-stone-400" size={16} />}
                <span>
                  <span className="font-semibold">{entry.task?.label ?? entry.task_type}</span> · ~{Math.round(entry.minutes)} min
                  <span className="block text-xs text-[var(--muted)]">{entry.reason}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
        <section className="min-w-0 rounded-2xl border bg-white/60 p-5">
          {drill.status === "paused" ? <p className="text-[var(--muted)]">Paused. Resume when you&apos;re ready.</p> : null}
          {!item && drill.status !== "paused" ? (
            drill.current_index != null ? (
              <Button onClick={() => void openItem(drill.items[drill.current_index!].task_id)}>Start next item</Button>
            ) : (
              <div>
                <p className="font-semibold">All items done.</p>
                <Button className="mt-3" disabled={busy} onClick={() => void act("complete")}>Finish drill</Button>
              </div>
            )
          ) : null}
          {item ? (
            <>
              <ReviewRunner item={item} onChange={(next) => { setItem(next); if (next.status === "submitted") void refresh(drill.id); }} />
              {item.status === "submitted" ? <Button className="mt-5" onClick={() => { setItem(null); void refresh(drill.id); }}>Next</Button> : null}
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
