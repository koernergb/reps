"use client";

import { AlarmClockOff, ArrowRight, Flag, LoaderCircle, SkipForward } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { errorMessage, getReviewQueue, reportTask, skipTask, snoozeTask, startReview, type ReviewTaskView } from "@/lib/api";

function TaskCard({ task, onStart, onChanged, due }: { task: ReviewTaskView; onStart: () => void; onChanged: () => void; due: boolean }) {
  const [busy, setBusy] = useState(false);
  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    try { await action(); onChanged(); } finally { setBusy(false); }
  }
  return (
    <li className="rounded-2xl border bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-green-800">{task.label} · ~{Math.round(task.estimated_minutes)} min</p>
          <p className="mt-1 font-bold">{task.capability.name}</p>
          <p className="mt-1 text-sm text-[var(--muted)]">{task.reason}</p>
          {!due ? <p className="mt-1 text-xs text-[var(--muted)]">Due {new Date(task.due_at).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</p> : null}
        </div>
        {due ? <Button disabled={busy} onClick={onStart}>Start <ArrowRight aria-hidden className="ml-1" size={15} /></Button> : null}
      </div>
      {due ? (
        <div className="mt-3 flex flex-wrap gap-1">
          <Button disabled={busy} onClick={() => void act(() => snoozeTask(task.id, 1))} variant="ghost"><AlarmClockOff aria-hidden className="mr-1" size={14} /> Tomorrow</Button>
          <Button disabled={busy} onClick={() => void act(() => skipTask(task.id))} variant="ghost"><SkipForward aria-hidden className="mr-1" size={14} /> Skip</Button>
          <Button disabled={busy} onClick={() => { const reason = window.prompt("What's wrong with this exercise?"); if (reason && reason.trim().length >= 3) void act(() => reportTask(task.id, reason)); }} variant="ghost"><Flag aria-hidden className="mr-1" size={14} /> Report broken</Button>
        </div>
      ) : null}
    </li>
  );
}

export default function ReviewsPage() {
  const router = useRouter();
  const [queue, setQueue] = useState<{ due: ReviewTaskView[]; upcoming: ReviewTaskView[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    getReviewQueue().then(setQueue).catch((reason: unknown) => setError(errorMessage(reason, "Could not load reviews.")));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function start(task: ReviewTaskView) {
    try {
      const item = await startReview(task.id);
      if (item.kind === "interview" && item.interview_session_id) router.push(`/interviews/${item.interview_session_id}`);
      else router.push(`/reviews/${item.attempt_id}`);
    } catch (reason) {
      setError(errorMessage(reason, "Could not start the review."));
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Spaced remediation</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight">Reviews</h1>
      <p className="mt-3 text-[var(--muted)]">Each item targets a specific capability from your interviews. Reviews become due at 4 a.m. in your time zone.</p>
      {error ? <p className="mt-6 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
      {!queue && !error ? <p className="mt-8 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading…</p> : null}
      {queue ? (
        <>
          <h2 className="mt-10 text-lg font-bold">Due today ({queue.due.length})</h2>
          {queue.due.length === 0 ? <p className="mt-3 text-[var(--muted)]">Nothing due. A drill will pick practice from your weakest areas.</p> : null}
          <ul className="mt-3 grid gap-3">{queue.due.map((task) => <TaskCard due key={task.id} onChanged={load} onStart={() => void start(task)} task={task} />)}</ul>
          <h2 className="mt-10 text-lg font-bold">Coming up</h2>
          <ul className="mt-3 grid gap-3">{queue.upcoming.map((task) => <TaskCard due={false} key={task.id} onChanged={load} onStart={() => undefined} task={task} />)}</ul>
          {queue.upcoming.length === 0 ? <p className="mt-3 text-[var(--muted)]">No upcoming reviews.</p> : null}
        </>
      ) : null}
    </div>
  );
}
