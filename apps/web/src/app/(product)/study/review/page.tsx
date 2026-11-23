"use client";

import { CheckCircle2, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  errorMessage,
  getStudyQueue,
  reviewStudyCard,
  type StudyCard,
  type StudyQueueMode,
  type StudyReviewResult,
} from "@/lib/api";

const CONFIDENCE_LABELS = [
  "Blank",
  "Guess",
  "Shaky",
  "OK",
  "Solid",
  "Crystal",
] as const;

function formatInterval(days: number): string {
  if (days < 1 / 24) return `${Math.max(1, Math.round(days * 24 * 60))} min`;
  if (days < 1) return `${Math.round(days * 24)} hr`;
  if (days < 1.05) return "1 day";
  return `${days.toFixed(days < 10 ? 1 : 0)} days`;
}

function ReviewSession() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const courseId = searchParams.get("course") ?? undefined;
  const modeParam = searchParams.get("mode");
  const mode: StudyQueueMode = modeParam === "practice" ? "practice" : "due";

  const [cards, setCards] = useState<StudyCard[] | null>(null);
  const [courseName, setCourseName] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<StudyReviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setCards(null);
    setIndex(0);
    setAnswer("");
    setResult(null);
    setError(null);
    try {
      const queue = await getStudyQueue({ courseId, mode });
      setCards(queue.due);
      setCourseName(queue.course_name);
    } catch (reason) {
      setError(errorMessage(reason, "Could not load cards."));
      setCards([]);
    }
  }, [courseId, mode]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const card = cards?.[index];

  function setMode(next: StudyQueueMode) {
    const params = new URLSearchParams();
    if (courseId) params.set("course", courseId);
    params.set("mode", next);
    router.replace(`/study/review?${params.toString()}`);
  }

  async function submit(confidence: number) {
    if (!card || !answer.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const graded = await reviewStudyCard(card.id, { answer: answer.trim(), confidence });
      setResult(graded);
    } catch (reason) {
      setError(errorMessage(reason, "Could not grade that review."));
    } finally {
      setBusy(false);
    }
  }

  function nextCard() {
    setIndex((value) => value + 1);
    setAnswer("");
    setResult(null);
  }

  if (!cards && !error) {
    return (
      <p className="flex items-center gap-2 text-[var(--muted)]">
        <LoaderCircle className="animate-spin" size={18} /> Building today&apos;s queue…
      </p>
    );
  }
  if (error && !card && cards?.length === 0) {
    return (
      <div>
        <p className="rounded-lg bg-red-50 p-3 text-red-900" role="alert">
          {error}
        </p>
        <Link className="mt-4 inline-block text-sm font-bold text-green-800" href="/study">
          Back to study
        </Link>
      </div>
    );
  }
  if (!card) {
    return (
      <div className="mx-auto max-w-xl rounded-3xl border bg-white p-10 text-center">
        <CheckCircle2 className="mx-auto text-green-700" size={42} />
        <h1 className="mt-4 text-3xl font-bold">
          {mode === "practice" ? "Practice queue empty" : "You're caught up"}
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          {mode === "practice"
            ? "No active cards in this scope yet."
            : `Reviewed ${index} card${index === 1 ? "" : "s"}. Reps will bring them back when recall starts to fade.`}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {mode === "due" && courseId ? (
            <Button onClick={() => setMode("practice")} variant="secondary">
              Practice all in this course
            </Button>
          ) : null}
          <Link
            className="inline-block rounded-lg bg-green-800 px-4 py-2 text-sm font-bold text-white"
            href="/study"
          >
            Return to courses
          </Link>
        </div>
      </div>
    );
  }

  const canSubmit = answer.trim().length > 0 && !busy && !result;
  const scopeLabel = courseName ?? "All courses";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--muted)]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-bold text-stone-800">
            {scopeLabel}
          </span>
          <span>
            {card.concept} · {card.card_type}
          </span>
        </div>
        <span>
          {index + 1} / {cards.length}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg border bg-white p-0.5 text-sm">
          <button
            className={`rounded-md px-3 py-1.5 font-semibold ${
              mode === "due" ? "bg-green-800 text-white" : "text-stone-600 hover:bg-stone-50"
            }`}
            onClick={() => setMode("due")}
            type="button"
          >
            Due only
          </button>
          <button
            className={`rounded-md px-3 py-1.5 font-semibold ${
              mode === "practice" ? "bg-green-800 text-white" : "text-stone-600 hover:bg-stone-50"
            }`}
            onClick={() => setMode("practice")}
            type="button"
          >
            Practice all
          </button>
        </div>
        <Link className="text-sm font-semibold text-green-800 hover:underline" href="/study">
          Change course
        </Link>
      </div>

      <div className="mt-3 h-1 overflow-hidden rounded bg-stone-200">
        <div
          className="h-full bg-green-700 transition-all"
          style={{ width: `${((index + 1) / cards.length) * 100}%` }}
        />
      </div>

      <section className="mt-8 min-h-80 rounded-3xl border bg-white p-8 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-wider text-green-800">Prompt</p>
        <h1 className="mt-4 text-2xl font-bold leading-relaxed">{card.prompt}</h1>

        <label className="mt-8 block">
          <span className="text-xs font-bold uppercase tracking-wider text-green-800">
            Your answer
          </span>
          <textarea
            className="mt-2 w-full rounded-xl border p-4 focus-visible:outline-2 focus-visible:outline-green-800 disabled:bg-stone-50"
            disabled={Boolean(result) || busy}
            onChange={(event) => setAnswer(event.target.value)}
            placeholder="Type what you remember…"
            rows={5}
            value={answer}
          />
        </label>

        {error ? (
          <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-900" role="alert">
            {error}
          </p>
        ) : null}

        {!result ? (
          <div className="mt-8">
            <p className="text-sm font-semibold">How sure are you? (0–5)</p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Rate before feedback. Wrong answers still come back soon even if you felt sure.
            </p>
            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
              {CONFIDENCE_LABELS.map((label, confidence) => (
                <Button
                  disabled={!canSubmit}
                  key={label}
                  onClick={() => void submit(confidence)}
                  variant={confidence <= 1 ? "secondary" : "default"}
                >
                  <span className="flex flex-col items-center gap-0.5 leading-none">
                    <span className="text-base font-bold">{confidence}</span>
                    <span className="text-[10px] font-medium opacity-80">{label}</span>
                  </span>
                </Button>
              ))}
            </div>
            {busy ? (
              <p className="mt-4 flex items-center gap-2 text-sm text-[var(--muted)]">
                <LoaderCircle className="animate-spin" size={16} /> Grading…
              </p>
            ) : null}
          </div>
        ) : (
          <div className="mt-8 border-t pt-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-xs font-bold uppercase tracking-wider text-green-800">Result</p>
              <p className="text-sm text-[var(--muted)]">
                Score {Math.round(result.correctness * 100)}% · confidence {result.confidence}/5 ·
                next in {formatInterval(result.interval_days)}
              </p>
            </div>
            <p
              className={`mt-3 text-lg font-semibold ${
                result.correctness >= 0.8
                  ? "text-green-800"
                  : result.correctness >= 0.45
                    ? "text-amber-800"
                    : "text-red-800"
              }`}
            >
              {result.feedback}
            </p>
            <p className="mt-6 text-xs font-bold uppercase tracking-wider text-green-800">
              Expected answer
            </p>
            <p className="mt-2 whitespace-pre-wrap text-lg">{result.expected_answer}</p>
            <Button className="mt-8" onClick={nextCard}>
              Next card
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}

export default function StudyReviewPage() {
  return (
    <Suspense
      fallback={
        <p className="flex items-center gap-2 text-[var(--muted)]">
          <LoaderCircle className="animate-spin" size={18} /> Loading review…
        </p>
      }
    >
      <ReviewSession />
    </Suspense>
  );
}
