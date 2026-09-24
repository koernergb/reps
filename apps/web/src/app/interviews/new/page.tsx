"use client";

import { LoaderCircle, Shuffle, Timer, Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { LocalModeBanner } from "@/components/local-mode-banner";
import { Button } from "@/components/ui/button";
import { errorMessage, getSettings, listInterviews, listProblems, startInterview, type LearnerSettings, type ProblemSummary } from "@/lib/api";
import { cn } from "@/lib/cn";

const MODES = {
  practice: {
    title: "Practice",
    icon: Users,
    points: ["Up to 5 progressively specific hints", "Generous clarifications and check-ins", "No time limit", "Counts less toward independence"],
  },
  mock: {
    title: "Mock interview",
    icon: Timer,
    points: ["45-minute server-enforced time limit", "One small nudge at most", "Minimal clarifications, no teaching", "Scored on a 5-part scorecard"],
  },
} as const;

function NewInterview() {
  const router = useRouter();
  const params = useSearchParams();
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [seen, setSeen] = useState<Set<string>>(new Set());
  const [settings, setSettings] = useState<LearnerSettings | null>(null);
  const [slug, setSlug] = useState(params.get("problem") ?? "");
  const [mode, setMode] = useState<"practice" | "mock">(params.get("mode") === "mock" ? "mock" : "practice");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([listProblems(), listInterviews(), getSettings()])
      .then(([loaded, history, prefs]) => {
        setProblems(loaded);
        setSeen(new Set(history.map((item) => item.problem_slug)));
        setSettings(prefs);
      })
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load problems.")));
  }, []);

  const unseen = useMemo(() => problems.filter((problem) => !seen.has(problem.slug)), [problems, seen]);
  const chosen = problems.find((problem) => problem.slug === slug);

  function surprise() {
    const pool = unseen.length ? unseen : problems;
    if (pool.length) setSlug(pool[Math.floor(Math.random() * pool.length)].slug);
  }

  async function begin() {
    if (!slug) return;
    setBusy(true);
    setError(null);
    try {
      const view = await startInterview({
        problem_slug: slug,
        mode,
        time_multiplier: settings?.mock_time_multiplier ?? 1,
        reduce_motion: settings?.reduce_timer_motion ?? false,
      });
      router.push(`/interviews/${view.id}`);
    } catch (reason) {
      setError(errorMessage(reason, "Could not start the interview."));
      setBusy(false);
    }
  }

  const minutes = Math.round(45 * (settings?.mock_time_multiplier ?? 1));
  return (
    <div className="mx-auto max-w-4xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">New interview</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight">Choose a mode</h1>
      <p className="mt-3 text-[var(--muted)]">The mode is fixed once the interview starts.</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2" role="radiogroup" aria-label="Interview mode">
        {(Object.keys(MODES) as Array<keyof typeof MODES>).map((key) => {
          const { title, icon: Icon, points } = MODES[key];
          return (
            <button
              aria-checked={mode === key}
              className={cn("rounded-2xl border bg-white p-6 text-left transition focus-visible:outline-2 focus-visible:outline-green-800", mode === key ? "border-green-700 ring-2 ring-green-700" : "hover:border-green-300")}
              key={key}
              onClick={() => setMode(key)}
              role="radio"
              type="button"
            >
              <Icon aria-hidden className="text-green-800" />
              <p className="mt-4 text-lg font-bold">{title}</p>
              <ul className="mt-3 space-y-1 text-sm text-[var(--muted)]">
                {points.map((point) => <li key={point}>• {key === "mock" && point.startsWith("45") ? `${minutes}-minute server-enforced time limit` : point}</li>)}
              </ul>
            </button>
          );
        })}
      </div>
      <section className="mt-8 rounded-2xl border bg-white p-6">
        <label className="font-bold" htmlFor="problem">Problem</label>
        <div className="mt-3 flex flex-wrap gap-2">
          <select className="min-w-0 flex-1 rounded-lg border px-3 py-2" id="problem" onChange={(event) => setSlug(event.target.value)} value={slug}>
            <option value="">Select a problem…</option>
            {problems.map((problem) => (
              <option key={problem.slug} value={problem.slug}>{problem.title} ({problem.difficulty}){seen.has(problem.slug) ? " · seen" : ""}</option>
            ))}
          </select>
          <Button onClick={surprise} variant="secondary"><Shuffle aria-hidden className="mr-1.5" size={15} /> Unseen problem</Button>
        </div>
        {chosen && seen.has(chosen.slug) ? <p className="mt-2 text-sm text-amber-900">You&apos;ve seen this problem before; results count less toward transfer.</p> : null}
        <p className="mt-2 text-xs text-[var(--muted)]">The interview hides the pattern name so recognizing it is part of the exercise.</p>
      </section>
      {error ? <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-900" role="alert">{error}</p> : null}
      <Button className="mt-6" disabled={!slug || busy} onClick={begin}>
        {busy ? <LoaderCircle aria-hidden className="mr-2 animate-spin" size={16} /> : null} Start {mode === "mock" ? "mock interview" : "practice interview"}
      </Button>
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <LocalModeBanner />
      <Suspense fallback={<p>Loading…</p>}>
        <NewInterview />
      </Suspense>
    </AppShell>
  );
}
