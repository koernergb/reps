"use client";

import { ArrowLeft, LoaderCircle, MessagesSquare, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { SolutionReveal } from "@/components/solution-reveal";
import { Button } from "@/components/ui/button";
import { Workspace } from "@/components/workspace/workspace";
import { errorMessage, getProblem, getProblemProgress, type ProblemDetail } from "@/lib/api";
import { clearDraft, loadDraft, saveDraft } from "@/lib/drafts";
import { useExecution } from "@/lib/use-execution";

export default function ProblemPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const router = useRouter();
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<Awaited<ReturnType<typeof getProblemProgress>>["stages"]>([]);
  const { execution, error: executionError, pending, execute } = useExecution(slug);
  const draftScope = `practice:${slug}`;

  useEffect(() => {
    getProblem(slug)
      .then((loaded) => {
        setProblem(loaded);
        setCode(loadDraft(draftScope) ?? loaded.starter_code);
      })
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load the problem.")));
    getProblemProgress(slug).then((progress) => setStages(progress.stages)).catch(() => undefined);
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
        <div className="flex flex-wrap gap-2">
          <SolutionReveal onViewed={() => getProblemProgress(slug).then((progress) => setStages(progress.stages)).catch(() => undefined)} slug={slug} />
          <Button onClick={() => { if (window.confirm("Replace your draft with the starter code?")) { clearDraft(draftScope); setCode(problem.starter_code); } }} variant="ghost"><RotateCcw aria-hidden className="mr-1.5" size={15} /> Reset code</Button>
          <Button onClick={() => router.push(`/interviews/new?problem=${encodeURIComponent(slug)}`)} variant="secondary"><MessagesSquare aria-hidden className="mr-1.5" size={15} /> Practice as an interview</Button>
        </div>
      </div>
      {stages.length ? (
        <ol aria-label="Remediation progress" className="mb-3 flex flex-wrap gap-2 text-xs">
          {stages.map((stage) => (
            <li className={stage.status === "done" ? "rounded-full bg-green-100 px-2 py-1 font-semibold text-green-900" : "rounded-full bg-stone-100 px-2 py-1 text-stone-700"} key={stage.stage}>
              {stage.label}: {stage.status === "done" ? "done" : stage.status === "scheduled" ? "scheduled" : "—"}
            </li>
          ))}
        </ol>
      ) : null}
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
