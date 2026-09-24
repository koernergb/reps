"use client";

import { CheckCircle2, CircleAlert, Lightbulb, LoaderCircle, MessagesSquare, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Workspace } from "@/components/workspace/workspace";
import { answerReview, confirmReview, errorMessage, getProblem, reviewHint, type ProblemDetail, type ReviewItem } from "@/lib/api";
import { loadDraft, saveDraft } from "@/lib/drafts";
import { useExecution } from "@/lib/use-execution";

const BAND_STYLE = {
  correct: { icon: CheckCircle2, tone: "bg-green-50 text-green-950", label: "Correct" },
  partial: { icon: CircleAlert, tone: "bg-amber-50 text-amber-950", label: "Partly correct" },
  missed: { icon: XCircle, tone: "bg-red-50 text-red-950", label: "Not yet" },
};

function Hints({ item, onHint, busy }: { item: ReviewItem; onHint: () => void; busy: boolean }) {
  const left = item.hints_total - item.hints_used;
  return (
    <div className="mt-4">
      {item.hints.map((hint, index) => <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm ring-1 ring-amber-200" key={index}><strong>Hint {index + 1}:</strong> {hint}</p>)}
      {item.status === "in_progress" && left > 0 ? (
        <Button className="mt-2" disabled={busy} onClick={onHint} variant="ghost"><Lightbulb aria-hidden className="mr-1" size={15} /> {item.hints_used ? "Another hint" : "I'm stuck — hint"} ({left} left)</Button>
      ) : null}
      {item.hints_used ? <p className="mt-1 text-xs text-[var(--muted)]">Hints are recorded and reduce how much this counts toward independence.</p> : null}
    </div>
  );
}

function Feedback({ item, onConfirm, busy }: { item: ReviewItem; onConfirm: (answer: string) => void; busy: boolean }) {
  const [answer, setAnswer] = useState("");
  const result = item.result;
  if (!result) return null;
  const style = BAND_STYLE[result.band];
  const Icon = style.icon;
  return (
    <div aria-live="polite" className="mt-5 space-y-3">
      <div className={`rounded-xl p-4 ${style.tone}`}>
        <p className="flex items-center gap-2 font-bold"><Icon aria-hidden size={18} /> {style.label}</p>
        <p className="mt-1 text-sm">{result.feedback}</p>
        {result.missing_points.length ? <p className="mt-1 text-sm">Missing: {result.missing_points.join(", ")}</p> : null}
      </div>
      {result.reference_answer ? <p className="rounded-xl border bg-white p-4 text-sm"><strong>Reference:</strong> {result.reference_answer}</p> : null}
      {result.rebuild ? (
        <section className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm">
          <p className="font-bold">Let&apos;s rebuild this idea</p>
          <p className="mt-1"><strong>Common misconception:</strong> {result.rebuild.misconception}</p>
          <p className="mt-1">{result.rebuild.explanation}</p>
          {result.rebuild.confirmation_question && !result.confirmation ? (
            <div className="mt-3">
              <label className="font-semibold" htmlFor="confirm-answer">{result.rebuild.confirmation_question}</label>
              <textarea className="mt-2 w-full rounded-lg border bg-white p-2" id="confirm-answer" onChange={(event) => setAnswer(event.target.value)} rows={3} value={answer} />
              <Button className="mt-2" disabled={busy || !answer.trim()} onClick={() => onConfirm(answer)}>Check my understanding</Button>
            </div>
          ) : null}
          {result.confirmation ? <p className="mt-3 font-semibold">{result.confirmation.feedback}</p> : null}
        </section>
      ) : null}
      <p className="text-xs text-[var(--muted)]">Graded by {result.grader}. Your next review of this skill has been scheduled.</p>
    </div>
  );
}

function CodeItem({ item, onDone }: { item: ReviewItem; onDone: (next: ReviewItem) => void }) {
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const scope = `review:${item.attempt_id}`;
  const [code, setCode] = useState(() => loadDraft(scope) ?? item.starter_code ?? "");
  const [error, setError] = useState<string | null>(null);
  const { execution, error: executionError, pending, execute } = useExecution(item.problem_slug ?? "");
  useEffect(() => {
    if (item.problem_slug) getProblem(item.problem_slug).then(setProblem).catch(() => setError("Could not load the problem."));
  }, [item.problem_slug]);
  const lastSubmit = execution?.kind === "submit" && execution.status === "completed" ? execution : null;
  async function finish() {
    if (!lastSubmit) return;
    try {
      onDone(await answerReview(item.attempt_id, { job_id: lastSubmit.id }));
    } catch (reason) {
      setError(errorMessage(reason, "Could not record the result."));
    }
  }
  if (!problem) return <p className="flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={16} /> Loading…</p>;
  return (
    <div className="mt-4">
      {error ? <p className="mb-2 text-sm text-red-800" role="alert">{error}</p> : null}
      <Workspace
        code={code}
        disabled={item.status !== "in_progress"}
        execution={execution}
        executionError={executionError}
        onCodeChange={(next) => { setCode(next); saveDraft(scope, next); }}
        onRun={() => void execute("run", code)}
        onSubmit={() => void execute("submit", code)}
        pending={pending}
        problem={problem}
        revealTopic={item.task_type !== "transfer"}
        storageId="review"
        toolbar={item.status === "in_progress" ? <Button className="bg-green-600 hover:bg-green-700" disabled={!lastSubmit || pending !== null} onClick={finish}>Finish with this submission</Button> : null}
      />
    </div>
  );
}

export function ReviewRunner({ item, onChange }: { item: ReviewItem; onChange: (item: ReviewItem) => void }) {
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<ReviewItem>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await action());
    } catch (reason) {
      setError(errorMessage(reason, "That didn't work."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article>
      {item.task ? <p className="text-xs font-bold uppercase tracking-wider text-green-800">{item.task.label} · {item.task.capability.name}</p> : null}
      {item.task ? <p className="mt-1 text-xs text-[var(--muted)]">Why now: {item.task.reason}</p> : null}
      <h2 className="mt-3 whitespace-pre-wrap text-xl font-bold leading-8">{item.prompt}</h2>
      {error ? <p className="mt-3 text-sm text-red-800" role="alert">{error}</p> : null}
      {item.kind === "interview" ? (
        <div className="mt-4">
          <Button asChild><Link href={`/interviews/${item.interview_session_id}`}><MessagesSquare aria-hidden className="mr-1.5" size={16} /> Open the interview</Link></Button>
          <p className="mt-2 text-sm text-[var(--muted)]">This item completes when the interview report is ready.</p>
        </div>
      ) : null}
      {item.kind === "code" ? <CodeItem item={item} onDone={onChange} /> : null}
      {item.kind === "text" ? (
        <>
          <Hints busy={busy} item={item} onHint={() => void run(() => reviewHint(item.attempt_id))} />
          {item.status === "in_progress" ? (
            <form className="mt-4" onSubmit={(event) => { event.preventDefault(); void run(() => answerReview(item.attempt_id, { answer, confidence })); }}>
              <label className="sr-only" htmlFor="review-answer">Your answer</label>
              <textarea className="w-full rounded-xl border bg-white p-3 text-sm focus:outline-2 focus:outline-green-700" id="review-answer" onChange={(event) => setAnswer(event.target.value)} placeholder="Answer in your own words…" rows={5} value={answer} />
              <label className="mt-3 block text-sm" htmlFor="confidence">How confident are you? <strong>{confidence}/5</strong></label>
              <input className="w-48 accent-green-700" id="confidence" max={5} min={1} onChange={(event) => setConfidence(Number(event.target.value))} type="range" value={confidence} />
              <div className="mt-3"><Button disabled={busy || !answer.trim()} type="submit">{busy ? <LoaderCircle aria-hidden className="mr-2 animate-spin" size={15} /> : null} Check answer</Button></div>
            </form>
          ) : null}
        </>
      ) : null}
      <Feedback busy={busy} item={item} onConfirm={(text) => void run(() => confirmReview(item.attempt_id, text))} />
    </article>
  );
}
