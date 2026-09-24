"use client";

import { ArrowLeft, LoaderCircle, MessagesSquare, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Workspace } from "@/components/workspace/workspace";
import { errorMessage, getProblem, type ProblemDetail } from "@/lib/api";
import { clearDraft, loadDraft, saveDraft } from "@/lib/drafts";
import { useExecution } from "@/lib/use-execution";

export default function ProblemPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const router = useRouter();
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { execution, error: executionError, pending, execute } = useExecution(slug);
  const draftScope = `practice:${slug}`;

  useEffect(() => {
    getProblem(slug)
      .then((loaded) => {
        setProblem(loaded);
        setCode(loadDraft(draftScope) ?? loaded.starter_code);
      })
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load the problem.")));
  }, [slug, draftScope]);

  function updateCode(next: string) {
    setCode(next);
    saveDraft(draftScope, next);
  }

  if (error) return <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-950" role="alert">{error}</div>;
  if (!problem) return <p className="flex items-center gap-2 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading problem…</p>;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-green-800 hover:underline" href="/problems"><ArrowLeft aria-hidden size={16} /> All problems</Link>
        <div className="flex gap-2">
          <Button onClick={() => { if (window.confirm("Replace your draft with the starter code?")) { clearDraft(draftScope); setCode(problem.starter_code); } }} variant="ghost"><RotateCcw aria-hidden className="mr-1.5" size={15} /> Reset code</Button>
          <Button onClick={() => router.push(`/interviews/new?problem=${encodeURIComponent(slug)}`)} variant="secondary"><MessagesSquare aria-hidden className="mr-1.5" size={15} /> Practice as an interview</Button>
        </div>
      </div>
      <Workspace
        code={code}
        execution={execution}
        executionError={executionError}
        onCodeChange={updateCode}
        onRun={() => void execute("run", code)}
        onSubmit={() => void execute("submit", code)}
        pending={pending}
        problem={problem}
        storageId="practice"
      />
    </div>
  );
}
