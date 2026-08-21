"use client";

import { ArrowLeft, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { getProblem, type ProblemDetail } from "@/lib/api";

export default function ProblemPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProblem(slug)
      .then(setProblem)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load the problem."));
  }, [slug]);

  if (error) return <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-950" role="alert">{error}</div>;
  if (!problem) return <p className="flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading problem…</p>;

  return (
    <article className="mx-auto max-w-5xl">
      <Link className="inline-flex items-center gap-2 text-sm font-semibold text-green-800 hover:underline" href="/problems"><ArrowLeft aria-hidden size={16} /> All problems</Link>
      <div className="mt-7 flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]"><span>{problem.difficulty}</span><span aria-hidden>·</span><span>{problem.language}</span><span className="rounded-full bg-amber-100 px-2 py-1 text-amber-900">Development content</span></div>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">{problem.title}</h1>
      <p className="mt-6 max-w-3xl text-lg leading-8">{problem.statement}</p>
      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_0.8fr]">
        <section><h2 className="text-lg font-bold">Examples</h2>{problem.examples.map((example, index) => <pre className="mt-3 overflow-x-auto rounded-xl border bg-white p-4 text-sm" key={index}>{JSON.stringify(example, null, 2)}</pre>)}</section>
        <section><h2 className="text-lg font-bold">Constraints</h2><ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-[var(--muted)]">{problem.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul></section>
      </div>
      <section className="mt-10"><h2 className="text-lg font-bold">Python starter</h2><pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-5 text-sm leading-6 text-slate-100"><code>{problem.starter_code}</code></pre><p className="mt-3 text-sm text-[var(--muted)]">Editor and execution arrive in Milestone 3. Hidden evaluator material is intentionally absent from this response.</p></section>
    </article>
  );
}
