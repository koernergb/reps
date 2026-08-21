"use client";

import { ArrowRight, Database, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { listProblems, type ProblemSummary } from "@/lib/api";

export default function ProblemsPage() {
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listProblems()
      .then(setProblems)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load problems."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Local corpus</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Problems</h1>
      <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--muted)]">The first development problems validate the domain model. They are not promoted to the reviewed corpus until Human Gate 2.</p>

      {loading ? <p className="mt-10 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading the local corpus…</p> : null}
      {error ? <div className="mt-10 rounded-xl border border-red-200 bg-red-50 p-5 text-red-950" role="alert"><p className="font-bold">The local API is not ready.</p><p className="mt-2 text-sm">{error}</p><code className="mt-3 block text-xs">make services-up &amp;&amp; make db-migrate &amp;&amp; pnpm db:seed</code></div> : null}
      {!loading && !error ? (
        <div className="mt-9 grid gap-4">
          {problems.map((problem) => (
            <Link className="group rounded-2xl border bg-white p-6 transition hover:border-green-300 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-green-800" href={`/problems/${problem.slug}`} key={problem.id}>
              <div className="flex items-start justify-between gap-5">
                <div>
                  <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]"><span>{problem.difficulty}</span><span aria-hidden>·</span><span>{problem.language}</span><span className="rounded-full bg-amber-100 px-2 py-1 text-amber-900">{problem.status}</span></div>
                  <h2 className="mt-3 text-xl font-bold">{problem.title}</h2>
                  <div className="mt-4 flex flex-wrap gap-2">{problem.capabilities.map((capability) => <span className="rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-900" key={capability.slug}>{capability.name}</span>)}</div>
                </div>
                <ArrowRight aria-hidden className="mt-1 shrink-0 text-green-800 transition group-hover:translate-x-1" />
              </div>
            </Link>
          ))}
          {problems.length === 0 ? <div className="rounded-2xl border border-dashed bg-white/70 p-8 text-[var(--muted)]"><Database aria-hidden /><p className="mt-4">The database is connected but contains no seeded problems. Run <code>pnpm db:seed</code>.</p></div> : null}
        </div>
      ) : null}
    </div>
  );
}
