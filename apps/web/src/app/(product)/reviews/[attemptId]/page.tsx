"use client";

import { ArrowLeft, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ReviewRunner } from "@/components/review/review-runner";
import { errorMessage, getReviewAttempt, type ReviewItem } from "@/lib/api";

export default function ReviewAttemptPage({ params }: { params: Promise<{ attemptId: string }> }) {
  const { attemptId } = use(params);
  const [item, setItem] = useState<ReviewItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getReviewAttempt(attemptId).then(setItem).catch((reason: unknown) => setError(errorMessage(reason, "Could not load this review.")));
  }, [attemptId]);
  return (
    <div className="mx-auto max-w-6xl">
      <Link className="inline-flex items-center gap-2 text-sm font-semibold text-green-800 hover:underline" href="/reviews"><ArrowLeft aria-hidden size={16} /> Reviews</Link>
      {error ? <p className="mt-4 rounded-lg bg-red-50 p-3 text-red-900" role="alert">{error}</p> : null}
      {!item && !error ? <p className="mt-6 flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading…</p> : null}
      {item ? <div className="mt-6"><ReviewRunner item={item} onChange={setItem} /></div> : null}
    </div>
  );
}
