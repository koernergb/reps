"use client";

import { ArrowRight, CalendarClock, LoaderCircle, MessagesSquare, Target, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BandBadge } from "@/components/ui/band";
import { Button } from "@/components/ui/button";
import { errorMessage, getDashboard, type Dashboard } from "@/lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getDashboard().then(setData).catch((reason: unknown) => setError(errorMessage(reason, "Could not load your dashboard.")));
  }, []);
  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Today</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Build independence, one rep at a time.</h1>
      {error ? <p className="mt-6 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
      <section className="mt-8 grid gap-5 md:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl bg-green-900 p-7 text-white">
          <Target aria-hidden />
          <h2 className="mt-6 text-2xl font-bold">Start a 10-minute drill</h2>
          <p className="mt-2 text-green-100">{data ? (data.due_count ? `${data.due_count} review${data.due_count === 1 ? "" : "s"} due, mixed with your weakest skills.` : "Practice from your weakest skills.") : "A focused mix based on weak capabilities and due reviews."}</p>
          <Button asChild className="mt-6 bg-white text-green-950 hover:bg-green-50" variant="primary"><Link href="/drills">Start drill <ArrowRight aria-hidden className="ml-2" size={17} /></Link></Button>
        </div>
        <div className="rounded-2xl border bg-white p-7">
          <MessagesSquare aria-hidden className="text-green-800" />
          <h2 className="mt-6 text-xl font-bold">Interview</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Practice with coaching, or simulate the real thing under time.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button asChild variant="secondary"><Link href="/interviews/new?mode=mock">Start mock interview</Link></Button>
            <Button asChild variant="ghost"><Link href="/interviews/new">Practice</Link></Button>
          </div>
        </div>
      </section>
      {!data && !error ? <p className="mt-8 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading…</p> : null}
      {data ? (
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          <section className="rounded-2xl border bg-white p-6">
            <h2 className="flex items-center gap-2 font-bold"><TrendingUp aria-hidden className="text-green-800" size={18} /> Weakest skills</h2>
            {data.weak_capabilities.length === 0 ? <p className="mt-3 text-sm text-[var(--muted)]">No weaknesses recorded yet. Your first interview builds this list.</p> : null}
            <ul className="mt-3 space-y-3">
              {data.weak_capabilities.map((item) => (
                <li key={item.slug}>
                  <div className="flex items-center gap-2"><BandBadge band={item.band} /><span className="text-sm font-semibold">{item.name}</span></div>
                  <p className="mt-1 text-xs text-[var(--muted)]">{item.topic.name} · {item.explanation}</p>
                </li>
              ))}
            </ul>
            <Link className="mt-4 inline-block text-sm font-semibold text-green-800 hover:underline" href="/history">All skills →</Link>
          </section>
          <section className="rounded-2xl border bg-white p-6">
            <h2 className="flex items-center gap-2 font-bold"><CalendarClock aria-hidden className="text-green-800" size={18} /> Upcoming reviews</h2>
            {data.upcoming.length + data.due.length === 0 ? <p className="mt-3 text-sm text-[var(--muted)]">Nothing scheduled.</p> : null}
            <ul className="mt-3 space-y-2 text-sm">
              {[...data.due, ...data.upcoming].slice(0, 6).map((task) => (
                <li className="flex justify-between gap-3" key={task.id}>
                  <span>{task.label} · {task.capability.name}</span>
                  <span className="shrink-0 text-[var(--muted)]">{new Date(task.due_at) <= new Date() ? "Due" : new Date(task.due_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                </li>
              ))}
            </ul>
            <Link className="mt-4 inline-block text-sm font-semibold text-green-800 hover:underline" href="/reviews">Review queue →</Link>
          </section>
          <section className="rounded-2xl border bg-white p-6">
            <h2 className="font-bold">Patterns</h2>
            {data.patterns.length === 0 ? <p className="mt-3 text-sm text-[var(--muted)]">No pattern data yet.</p> : null}
            <ul className="mt-3 grid grid-cols-2 gap-2 text-sm">
              {data.patterns.map((pattern) => <li className="flex items-center justify-between gap-2" key={pattern.slug}><span>{pattern.name}</span><BandBadge band={pattern.band} /></li>)}
            </ul>
          </section>
          <section className="rounded-2xl border bg-white p-6">
            <h2 className="font-bold">Recent interviews</h2>
            {data.recent_interviews.length === 0 ? <p className="mt-3 text-sm text-[var(--muted)]">None yet.</p> : null}
            <ul className="mt-3 space-y-2 text-sm">
              {data.recent_interviews.map((interview) => (
                <li key={interview.id}><Link className="hover:underline" href={interview.state === "COMPLETE" || interview.state === "ABANDONED" ? `/interviews/${interview.id}/report` : `/interviews/${interview.id}`}>{interview.problem_title} · {interview.mode} · {(interview.result ?? "in progress").replaceAll("_", " ")}</Link></li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </div>
  );
}
