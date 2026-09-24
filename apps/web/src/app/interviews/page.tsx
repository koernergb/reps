"use client";

import { ArrowRight, LoaderCircle, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { LocalModeBanner } from "@/components/local-mode-banner";
import { Button } from "@/components/ui/button";
import { errorMessage, listInterviews, type InterviewSummary } from "@/lib/api";

const RESULT: Record<string, string> = {
  solved_independently: "Solved independently",
  solved_with_minor_hints: "Solved, minor hints",
  solved_with_major_hints: "Solved, major hints",
  solved_after_solution_view: "Solved after solution",
  incomplete: "Incomplete",
  failed: "Not solved",
  timed_out: "Time ran out",
  abandoned: "Ended early",
  completed: "Completed",
};

export default function InterviewsPage() {
  const [items, setItems] = useState<InterviewSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    listInterviews().then(setItems).catch((reason: unknown) => setError(errorMessage(reason, "Could not load interviews.")));
  }, []);
  return (
    <AppShell>
      <LocalModeBanner />
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Interviews</p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight">Your interviews</h1>
          </div>
          <Button asChild><Link href="/interviews/new"><Plus aria-hidden className="mr-1.5" size={16} /> New interview</Link></Button>
        </div>
        {error ? <p className="mt-6 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
        {!items && !error ? <p className="mt-8 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading…</p> : null}
        {items && items.length === 0 ? <p className="mt-8 rounded-2xl border border-dashed bg-white/70 p-8 text-[var(--muted)]">No interviews yet. Your first interview creates the evidence your review plan is built from.</p> : null}
        <ul className="mt-8 grid gap-3">
          {items?.map((item) => {
            const active = item.state !== "COMPLETE" && item.state !== "ABANDONED";
            return (
              <li key={item.id}>
                <Link className="flex items-center justify-between gap-4 rounded-2xl border bg-white p-5 hover:border-green-300 focus-visible:outline-2 focus-visible:outline-green-800" href={active ? `/interviews/${item.id}` : `/interviews/${item.id}/report`}>
                  <div>
                    <p className="font-bold">{item.problem_title}</p>
                    <p className="mt-1 text-sm text-[var(--muted)]">{item.mode === "mock" ? "Mock" : "Practice"} · {new Date(item.started_at).toLocaleString()} · {active ? "In progress" : RESULT[item.result ?? ""] ?? item.result}</p>
                  </div>
                  <ArrowRight aria-hidden className="shrink-0 text-green-800" size={18} />
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </AppShell>
  );
}
