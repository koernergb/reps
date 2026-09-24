"use client";

import { ArrowRight, Database, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { errorMessage, listProblems, type ProblemSummary } from "@/lib/api";

export default function ProblemsPage() {
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listProblems()
      .then(setProblems)
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load problems.")))
      .finally(() => setLoading(false));
  }, []);

  const groups = useMemo(() => {
    const byTopic = new Map<string, ProblemSummary[]>();
    for (const problem of problems) {
      const key = problem.topic?.name ?? "Other";
      byTopic.set(key, [...(byTopic.get(key) ?? []), problem]);
    }
    return [...byTopic.entries()];
  }, [problems]);

  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Curated corpus</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Problems</h1>
      <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--muted)]">Browse by pattern for focused practice. Interviews and transfer checks hide the pattern so recognition is part of the test.</p>

      {loading ? <p className="mt-10 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading the corpus…</p> : null}
      {error ? <div className="mt-10 rounded-xl border border-red-200 bg-red-50 p-5 text-red-950" role="alert"><p className="font-bold">The local API is not ready.</p><p className="mt-2 text-sm">{error}</p><code className="mt-3 block text-xs">make services-up &amp;&amp; make db-migrate &amp;&amp; make db-seed</code></div> : null}
      {!loading && !error && problems.length === 0 ? <div className="mt-10 rounded-2xl border border-dashed bg-white/70 p-8 text-[var(--muted)]"><Database aria-hidden /><p className="mt-4">The database is connected but contains no problems. Run <code>make db-seed</code>.</p></div> : null}
      {groups.map(([topic, items]) => (
        <section className="mt-10" key={topic}>
          <h2 className="text-lg font-bold">{topic} <span className="font-normal text-[var(--muted)]">({items.length})</span></h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {items.map((problem) => (
              <Link className="group rounded-2xl border bg-white p-5 transition hover:border-green-300 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-green-800" href={`/problems/${problem.slug}`} key={problem.id}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
                      <span>{problem.difficulty}</span>
                      {problem.status !== "reviewed" ? <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">Unreviewed</span> : null}
                    </div>
                    <h3 className="mt-2 font-bold">{problem.title}</h3>
                  </div>
                  <ArrowRight aria-hidden className="mt-1 shrink-0 text-green-800 transition group-hover:translate-x-1" size={18} />
                </div>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
