"use client";

import { CheckCircle2, LoaderCircle, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { errorMessage, getStudyQueue, reviewStudyCard, type StudyCard } from "@/lib/api";

export default function StudyReviewPage() {
  const [cards, setCards] = useState<StudyCard[] | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { getStudyQueue().then((queue) => setCards(queue.due)).catch((reason: unknown) => setError(errorMessage(reason, "Could not load due cards."))); }, []);
  const card = cards?.[index];

  async function rate(rating: "again" | "hard" | "good" | "easy") {
    if (!card) return;
    setBusy(true);
    try { await reviewStudyCard(card.id, { answer, rating }); setIndex((value) => value + 1); setAnswer(""); setRevealed(false); }
    catch (reason) { setError(errorMessage(reason, "Could not save that review.")); }
    finally { setBusy(false); }
  }

  if (!cards && !error) return <p className="flex items-center gap-2 text-[var(--muted)]"><LoaderCircle className="animate-spin" size={18} /> Building today&apos;s queue…</p>;
  if (error) return <div><p className="rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p><Link className="mt-4 inline-block text-sm font-bold text-green-800" href="/study">Back to study</Link></div>;
  if (!card) return <div className="mx-auto max-w-xl rounded-3xl border bg-white p-10 text-center"><CheckCircle2 className="mx-auto text-green-700" size={42} /><h1 className="mt-4 text-3xl font-bold">You&apos;re caught up</h1><p className="mt-2 text-[var(--muted)]">Reviewed {index} card{index === 1 ? "" : "s"}. Reps will bring them back when recall starts to fade.</p><Link className="mt-6 inline-block rounded-lg bg-green-800 px-4 py-2 text-sm font-bold text-white" href="/study">Return to courses</Link></div>;

  return <div className="mx-auto max-w-3xl"><div className="flex items-center justify-between text-sm text-[var(--muted)]"><span>{card.concept} · {card.card_type}</span><span>{index + 1} / {cards.length}</span></div><div className="mt-3 h-1 overflow-hidden rounded bg-stone-200"><div className="h-full bg-green-700 transition-all" style={{ width: `${((index + 1) / cards.length) * 100}%` }} /></div><section className="mt-8 min-h-80 rounded-3xl border bg-white p-8 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-green-800">Prompt</p><h1 className="mt-4 text-2xl font-bold leading-relaxed">{card.prompt}</h1>{card.card_type === "typed" || card.card_type === "cloze" ? <textarea className="mt-8 w-full rounded-xl border p-4 focus-visible:outline-2 focus-visible:outline-green-800" onChange={(event) => setAnswer(event.target.value)} placeholder="Type your answer before revealing…" rows={4} value={answer} /> : null}{!revealed ? <Button className="mt-8" onClick={() => setRevealed(true)}>Reveal answer</Button> : <div className="mt-8 border-t pt-6"><p className="text-xs font-bold uppercase tracking-wider text-green-800">Answer</p><p className="mt-3 whitespace-pre-wrap text-lg">{card.answer}</p><p className="mt-8 text-sm font-semibold">How well did you remember it?</p><div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4"><Button disabled={busy} onClick={() => void rate("again")} variant="secondary"><RotateCcw size={15} /> Again</Button><Button disabled={busy} onClick={() => void rate("hard")} variant="secondary">Hard</Button><Button disabled={busy} onClick={() => void rate("good")}>Good</Button><Button disabled={busy} onClick={() => void rate("easy")} variant="secondary">Easy</Button></div></div>}</section></div>;
}
