"use client";

import { AlertTriangle, ArrowLeft, CheckCircle2, CircleDashed, Flag, LoaderCircle, RefreshCw } from "lucide-react";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { SeverityBadge } from "@/components/ui/band";
import { Button } from "@/components/ui/button";
import { ApiRequestError, errorMessage, flagReport, getReport, retryReport, type Claim, type InterviewReport } from "@/lib/api";

const RESULT_LABEL: Record<string, string> = {
  solved_independently: "Solved independently",
  solved_with_minor_hints: "Solved with minor hints",
  solved_with_major_hints: "Solved with major hints",
  solved_after_solution_view: "Solved after viewing the solution",
  incomplete: "Incomplete",
  failed: "Not solved",
  timed_out: "Time ran out",
  abandoned: "Ended early",
};

function Evidence({ ids, report }: { ids: string[]; report: InterviewReport }) {
  const items = ids.map((id) => report.evidence[id]).filter(Boolean);
  if (!items.length) return null;
  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer font-semibold text-green-800">Evidence ({items.length})</summary>
      <ul className="mt-2 space-y-1 text-[var(--muted)]">
        {items.map((item) => (
          <li key={item.sequence}>#{item.sequence} {item.type.replaceAll("_", " ")}{item.excerpt ? `: “${item.excerpt}”` : ""}</li>
        ))}
      </ul>
    </details>
  );
}

function Claims({ title, claims, report }: { title: string; claims: Claim[]; report: InterviewReport }) {
  if (!claims.length) return null;
  return (
    <section className="rounded-2xl border bg-white p-5">
      <h3 className="font-bold">{title}</h3>
      <ul className="mt-3 space-y-3 text-sm">
        {claims.map((claim) => (
          <li key={claim.text}>
            {claim.text}
            <Evidence ids={claim.evidence_event_ids} report={report} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function ReportPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const [data, setData] = useState<InterviewReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [flagging, setFlagging] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    getReport(sessionId)
      .then((report) => { setData(report); setPending(false); })
      .catch((reason_: unknown) => {
        if (reason_ instanceof ApiRequestError && reason_.code === "report_not_ready") setPending(true);
        else setError(errorMessage(reason_, "Could not load the report."));
      });
  }, [sessionId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(load, 2500);
    return () => window.clearInterval(timer);
  }, [pending, load]);

  async function submitFlag() {
    if (!reason.trim() || flagging === null) return;
    try {
      setData(await flagReport(sessionId, { capability_slug: flagging || null, reason }));
      setFlagging(null);
      setReason("");
    } catch (reason_) {
      setError(errorMessage(reason_, "Could not submit the report."));
    }
  }

  async function retry() {
    try {
      setData(await retryReport(sessionId));
    } catch (reason_) {
      setError(errorMessage(reason_, "Retry failed."));
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-green-800 hover:underline" href="/interviews"><ArrowLeft aria-hidden size={16} /> Interviews</Link>
        {error ? <p className="mt-4 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
        {pending ? <p className="mt-8 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Preparing your report…</p> : null}
        {data ? <Report data={data} flagging={flagging} onFlag={setFlagging} onRetry={retry} reason={reason} setReason={setReason} submitFlag={submitFlag} /> : null}
      </div>
    </AppShell>
  );
}

function Report({ data, flagging, onFlag, onRetry, reason, setReason, submitFlag }: { data: InterviewReport; flagging: string | null; onFlag: (value: string | null) => void; onRetry: () => void; reason: string; setReason: (value: string) => void; submitFlag: () => void }) {
  const { report } = data;
  const facts = report.facts;
  const flagged = new Set(data.flags.map((flag) => flag.capability_slug));
  return (
    <div>
      <p className="mt-6 text-sm font-bold uppercase tracking-[0.18em] text-green-800">{facts.mode === "mock" ? "Mock interview report" : "Practice interview report"}</p>
      <h1 className="mt-2 text-4xl font-bold tracking-tight">{RESULT_LABEL[facts.result] ?? facts.result}</h1>
      {data.status === "degraded" ? (
        <p className="mt-4 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-950" role="status">
          <AlertTriangle aria-hidden className="mt-0.5 shrink-0" size={16} /> The AI evaluator was unavailable, so interpretation below is rule-based. <Button className="ml-auto" onClick={onRetry} variant="secondary"><RefreshCw aria-hidden className="mr-1" size={14} /> Retry</Button>
        </p>
      ) : null}

      <section className="mt-8 rounded-2xl border bg-white p-5">
        <h2 className="font-bold">Facts <span className="font-normal text-[var(--muted)]">(from code execution and your actions — exact)</span></h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div><dt className="text-[var(--muted)]">Hidden tests</dt><dd className="font-semibold">{facts.best_hidden_passed}/{facts.hidden_total}</dd></div>
          <div><dt className="text-[var(--muted)]">Runs / submits</dt><dd className="font-semibold">{facts.runs} / {facts.submissions}</dd></div>
          <div><dt className="text-[var(--muted)]">Hints</dt><dd className="font-semibold">{facts.hints_used}{facts.max_hint_level ? ` (up to level ${facts.max_hint_level})` : ""}</dd></div>
          <div><dt className="text-[var(--muted)]">Duration</dt><dd className="font-semibold">{Math.round(facts.duration_s / 60)} min</dd></div>
          <div><dt className="text-[var(--muted)]">Complexity</dt><dd className="font-semibold">{facts.complexity_time_correct == null ? "Not discussed" : facts.complexity_time_correct && facts.complexity_space_correct ? "Correct" : "Needs work"}</dd></div>
          <div><dt className="text-[var(--muted)]">Solution viewed</dt><dd className="font-semibold">{facts.solution_viewed ? "Yes (assisted)" : "No"}</dd></div>
        </dl>
      </section>

      {report.scorecard ? (
        <section className="mt-5 rounded-2xl border bg-white p-5">
          <h2 className="font-bold">Scorecard <span className="font-normal text-[var(--muted)]">({report.scorecard.rubric_version})</span></h2>
          <dl className="mt-3 grid gap-3 sm:grid-cols-5">
            {(["correctness", "reasoning", "communication", "complexity", "independence"] as const).map((key) => (
              <div key={key}>
                <dt className="text-xs capitalize text-[var(--muted)]">{key}</dt>
                <dd className="text-2xl font-bold">{report.scorecard![key].score}<span className="text-sm font-normal text-[var(--muted)]">/4</span></dd>
                <dd className="text-xs text-[var(--muted)]">{report.scorecard![key].explanation}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      <h2 className="mt-10 text-xl font-bold">Interpretation</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        {report.interpretation_source === "llm" ? `AI interpretation (${data.model}, ${data.prompt_version}).` : "Rule-based interpretation."} Confidence: {report.confidence < 0.4 ? "low" : report.confidence < 0.7 ? "medium" : "high"}. Transfer readiness: {report.transfer_confidence}.
      </p>
      {report.notes.map((note) => <p className="mt-2 text-sm text-[var(--muted)]" key={note}>{note}</p>)}
      <div className="mt-5 grid gap-5">
        <Claims claims={report.strengths} report={data} title="Strengths" />
        <section className="rounded-2xl border bg-white p-5">
          <h3 className="font-bold">Weaknesses and what happens next</h3>
          {report.weaknesses.length === 0 ? <p className="mt-2 flex items-center gap-2 text-sm text-green-900"><CheckCircle2 aria-hidden size={16} /> No weaknesses diagnosed.</p> : null}
          <ul className="mt-3 space-y-4">
            {report.weaknesses.map((weakness) => (
              <li className={flagged.has(weakness.capability) ? "opacity-50" : undefined} key={weakness.capability}>
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={weakness.severity} />
                  <span className="font-semibold">{data.capability_names[weakness.capability] ?? weakness.capability}</span>
                  <span className="text-xs text-[var(--muted)]">{weakness.source === "facts" ? "from execution/hints" : weakness.source === "llm" ? "AI interpretation" : "rule-based"}</span>
                  {flagged.has(weakness.capability) ? <span className="text-xs font-semibold">Reported — excluded from your learner model</span> : (
                    <Button className="ml-auto" onClick={() => onFlag(weakness.capability)} variant="ghost"><Flag aria-hidden className="mr-1" size={13} /> Inaccurate?</Button>
                  )}
                </div>
                <p className="mt-1 text-sm">{weakness.explanation}</p>
                <Evidence ids={weakness.evidence_event_ids} report={data} />
              </li>
            ))}
          </ul>
          {data.scheduled.length ? (
            <div className="mt-5 border-t pt-4">
              <p className="text-sm font-semibold"><CircleDashed aria-hidden className="mr-1 inline" size={14} />Scheduled from this interview</p>
              <ul className="mt-2 space-y-1 text-sm">
                {data.scheduled.map((task) => (
                  <li key={`${task.task_type}-${task.due_at}`}>{new Date(task.due_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })} · {task.label} · {task.capability}{task.status !== "pending" ? ` (${task.status})` : ""}</li>
                ))}
              </ul>
              <Link className="mt-2 inline-block text-sm font-semibold text-green-800 underline" href="/reviews">Open reviews</Link>
            </div>
          ) : report.weaknesses.length ? (
            <p className="mt-4 text-sm text-[var(--muted)]">No extra reviews were needed; these skills are practiced in every interview.</p>
          ) : null}
        </section>
        <Claims claims={report.misconceptions} report={data} title="Possible misconceptions" />
        <section className="grid gap-5 sm:grid-cols-2">
          <div className="rounded-2xl border bg-white p-5"><h3 className="font-bold">Communication · {report.communication.rating}/4</h3><p className="mt-2 text-sm text-[var(--muted)]">{report.communication.summary}</p></div>
          <div className="rounded-2xl border bg-white p-5"><h3 className="font-bold">Reasoning · {report.reasoning.rating}/4</h3><p className="mt-2 text-sm text-[var(--muted)]">{report.reasoning.summary}</p></div>
        </section>
      </div>
      <div className="mt-8">
        <Button onClick={() => onFlag("")} variant="secondary"><Flag aria-hidden className="mr-1.5" size={15} /> Report an inaccurate diagnosis</Button>
      </div>
      {flagging !== null ? (
        <section className="mt-4 rounded-2xl border bg-white p-5">
          <label className="font-semibold" htmlFor="flag-reason">What is inaccurate{flagging ? ` about “${data.capability_names[flagging] ?? flagging}”` : ""}?</label>
          <textarea className="mt-2 w-full rounded-lg border p-2 text-sm" id="flag-reason" onChange={(event) => setReason(event.target.value)} rows={3} value={reason} />
          <p className="mt-1 text-xs text-[var(--muted)]">Flagged evidence is excluded from your learner model immediately.</p>
          <div className="mt-3 flex gap-2"><Button disabled={reason.trim().length < 3} onClick={submitFlag}>Submit</Button><Button onClick={() => onFlag(null)} variant="ghost">Cancel</Button></div>
        </section>
      ) : null}
      <p className="mt-10 text-xs text-[var(--muted)]">Evaluation {data.evaluation_id.slice(0, 8)} · {data.evaluator} · schema v{data.schema_version} · {new Date(data.created_at).toLocaleString()}</p>
    </div>
  );
}
