"use client";

import { CheckCircle2, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  errorMessage,
  getStudyQueue,
  reviewStudyCard,
  type StudyCard,
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

export default function StudyReviewPage() {
  const [cards, setCards] = useState<StudyCard[] | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<StudyReviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStudyQueue()
      .then((queue) => setCards(queue.due))
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load due cards.")));
  }, []);

  const card = cards?.[index];

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
  if (error && !card) {
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
        <h1 className="mt-4 text-3xl font-bold">You&apos;re caught up</h1>
        <p className="mt-2 text-[var(--muted)]">
          Reviewed {index} card{index === 1 ? "" : "s"}. Reps will bring them back when recall starts
          to fade.
        </p>
        <Link
          className="mt-6 inline-block rounded-lg bg-green-800 px-4 py-2 text-sm font-bold text-white"
          href="/study"
        >
          Return to courses
        </Link>
      </div>
    );
  }

  const canSubmit = answer.trim().length > 0 && !busy && !result;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between text-sm text-[var(--muted)]">
        <span>
          {card.concept} · {card.card_type}
        </span>
        <span>
          {index + 1} / {cards.length}
        </span>
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
