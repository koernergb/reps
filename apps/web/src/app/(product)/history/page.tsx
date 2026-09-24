"use client";

import { LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { BandBadge } from "@/components/ui/band";
import { errorMessage, getCapabilities, getCapabilityEvidence, getReviewHistory, type CapabilityStateView, type EvidenceView } from "@/lib/api";

const SOURCES = [
  { value: "", label: "All evidence" },
  { value: "interview", label: "Interviews" },
  { value: "review", label: "Reviews" },
];
const WINDOWS = [
  { value: 0, label: "All time" },
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
];

function EvidenceList({ slug }: { slug: string }) {
  const [source, setSource] = useState("");
  const [days, setDays] = useState(0);
  const [items, setItems] = useState<EvidenceView[] | null>(null);
  useEffect(() => {
    getCapabilityEvidence(slug, { source_type: source || undefined, days: days || undefined }).then(setItems).catch(() => setItems([]));
  }, [slug, source, days]);
  return (
    <div className="mt-3 rounded-xl bg-stone-50 p-3">
      <div className="flex flex-wrap gap-2 text-xs">
        <label className="sr-only" htmlFor={`source-${slug}`}>Evidence type</label>
        <select className="rounded border bg-white px-2 py-1" id={`source-${slug}`} onChange={(event) => setSource(event.target.value)} value={source}>{SOURCES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
        <label className="sr-only" htmlFor={`days-${slug}`}>Time window</label>
        <select className="rounded border bg-white px-2 py-1" id={`days-${slug}`} onChange={(event) => setDays(Number(event.target.value))} value={days}>{WINDOWS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
      </div>
      {!items ? <p className="mt-2 text-xs text-[var(--muted)]">Loading…</p> : null}
      <ul className="mt-2 space-y-1 text-xs">
        {items?.map((item) => (
          <li className={item.excluded ? "line-through opacity-60" : undefined} key={item.id}>
            {new Date(item.occurred_at).toLocaleDateString()} · {item.exercise_type.replaceAll("_", " ")}{item.problem_title ? ` (${item.problem_title})` : ""} · <strong>{item.outcome}</strong>
            {item.hint_level ? ` · hint L${item.hint_level}` : ""}{item.assisted ? " · assisted" : ""}{item.repeat_exposure ? " · repeat" : ""}{item.transfer ? " · transfer" : ""}
            {item.excluded ? " · excluded (reported)" : ""}
          </li>
        ))}
        {items && items.length === 0 ? <li className="text-[var(--muted)]">No evidence in this view.</li> : null}
      </ul>
    </div>
  );
}

export default function ProgressPage() {
  const [capabilities, setCapabilities] = useState<CapabilityStateView[] | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof getReviewHistory>>>([]);
  const [topic, setTopic] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getCapabilities(), getReviewHistory()])
      .then(([caps, reviews]) => { setCapabilities(caps); setHistory(reviews); })
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load progress.")));
  }, []);

  const topics = useMemo(() => [...new Map((capabilities ?? []).map((item) => [item.topic.slug, item.topic.name])).entries()], [capabilities]);
  const shown = (capabilities ?? []).filter((item) => !topic || item.topic.slug === topic);

  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Progress</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight">Skills and history</h1>
      <p className="mt-3 max-w-2xl text-[var(--muted)]">Bands summarize evidence without false precision. <strong>Strong</strong> requires repeated success including an independent interview or implementation; solution-assisted work never counts as transfer.</p>
      {error ? <p className="mt-6 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
      {!capabilities && !error ? <p className="mt-8 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading…</p> : null}
      {capabilities ? (
        <>
          <div className="mt-8 flex items-center gap-2">
            <label className="text-sm font-semibold" htmlFor="topic-filter">Pattern</label>
            <select className="rounded-lg border bg-white px-3 py-1.5 text-sm" id="topic-filter" onChange={(event) => setTopic(event.target.value)} value={topic}>
              <option value="">All</option>
              {topics.map(([slug, name]) => <option key={slug} value={slug}>{name}</option>)}
            </select>
          </div>
          {shown.length === 0 ? <p className="mt-6 text-[var(--muted)]">No skill evidence yet. Complete an interview or drill.</p> : null}
          <ul className="mt-4 grid gap-3">
            {shown.map((item) => (
              <li className="rounded-2xl border bg-white p-4" key={item.slug}>
                <button aria-expanded={open === item.slug} className="flex w-full flex-wrap items-center gap-2 text-left focus-visible:outline-2 focus-visible:outline-green-800" onClick={() => setOpen(open === item.slug ? null : item.slug)} type="button">
                  <BandBadge band={item.band} />
                  <span className="font-semibold">{item.name}</span>
                  <span className="text-xs text-[var(--muted)]">{item.topic.name} · {item.evidence_count} evidence · {item.confidence} confidence</span>
                  {item.next_review_at ? <span className="ml-auto text-xs text-[var(--muted)]">Retention check around {new Date(item.next_review_at).toLocaleDateString()}</span> : null}
                </button>
                <p className="mt-1 text-sm text-[var(--muted)]">{item.explanation}</p>
                {open === item.slug ? <EvidenceList slug={item.slug} /> : null}
              </li>
            ))}
          </ul>
          <h2 className="mt-12 text-xl font-bold">Recent reviews</h2>
          <ul className="mt-3 space-y-1 text-sm">
            {history.map((entry) => (
              <li key={entry.attempt_id}>{entry.completed_at ? new Date(entry.completed_at).toLocaleString() : ""} · {entry.task_type?.replaceAll("_", " ")} · {entry.capability} · <strong>{entry.band ?? "—"}</strong>{entry.hints_used ? ` · ${entry.hints_used} hint(s)` : ""}</li>
            ))}
            {history.length === 0 ? <li className="text-[var(--muted)]">No reviews completed yet.</li> : null}
          </ul>
        </>
      ) : null}
    </div>
  );
}
