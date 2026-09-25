"use client";

import { ArrowLeft, FileText, LoaderCircle, WifiOff } from "lucide-react";
import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";

import { InterviewerPanel } from "@/components/interview/interviewer-panel";
import { SolutionReveal } from "@/components/solution-reveal";
import { Button } from "@/components/ui/button";
import { Workspace } from "@/components/workspace/workspace";
import {
  ApiRequestError,
  advanceInterview,
  errorMessage,
  getInterview,
  getProblem,
  reportIdle,
  requestInterviewHint,
  saveInterviewCode,
  sendInterviewMessage,
  type InterviewState,
  type InterviewView,
  type ProblemDetail,
} from "@/lib/api";
import { loadDraft, saveDraft } from "@/lib/drafts";
import { useExecution } from "@/lib/use-execution";

const CHECKPOINT_MS = 4000;

export default function InterviewPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const [view, setView] = useState<InterviewView | null>(null);
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const lastActivity = useRef(0);
  const checkpoint = useRef<number | null>(null);
  const draftScope = `interview:${sessionId}`;
  const { execution, error: executionError, pending, execute } = useExecution(view?.problem_slug ?? "", sessionId);

  const refresh = useCallback(async () => {
    try {
      const next = await getInterview(sessionId);
      setView(next);
      setOffline(false);
      return next;
    } catch (reason) {
      if (reason instanceof ApiRequestError && reason.status === 0) setOffline(true);
      else setError(errorMessage(reason, "Could not load the interview."));
      return null;
    }
  }, [sessionId]);

  useEffect(() => {
    lastActivity.current = Date.now();
    getInterview(sessionId)
      .then((loaded) => {
        setView(loaded);
        setCode(loadDraft(draftScope) ?? loaded.current_code ?? "");
        return getProblem(loaded.problem_slug).then(setProblem);
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiRequestError && reason.status === 0) setOffline(true);
        else setError(errorMessage(reason, "Could not load the interview."));
      });
  }, [sessionId, draftScope]);

  // Reconnect: poll while offline, and resync when the tab becomes visible again.
  useEffect(() => {
    const onVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    const timer = offline ? window.setInterval(() => void refresh(), 3000) : undefined;
    return () => { document.removeEventListener("visibilitychange", onVisible); if (timer) window.clearInterval(timer); };
  }, [offline, refresh]);

  // Practice-mode check-in after sustained silence (the server applies the policy).
  useEffect(() => {
    if (!view || view.state === "COMPLETE" || view.state === "ABANDONED" || !view.policy.idle_checkin_s) return;
    const threshold = view.policy.idle_checkin_s;
    const timer = window.setInterval(() => {
      const idle = (Date.now() - lastActivity.current) / 1000;
      if (idle >= threshold) {
        lastActivity.current = Date.now();
        reportIdle(sessionId, view.version, idle).then(setView).catch(() => undefined);
      }
    }, 15_000);
    return () => window.clearInterval(timer);
  }, [view, sessionId]);

  async function act(action: () => Promise<InterviewView>) {
    setBusy(true);
    setError(null);
    lastActivity.current = Date.now();
    try {
      setView(await action());
    } catch (reason) {
      if (reason instanceof ApiRequestError && reason.code === "stale_version") {
        await refresh();
        setError("The interview changed in another tab or after a run. It has been refreshed; please retry.");
      } else if (reason instanceof ApiRequestError && reason.status === 0) {
        setOffline(true);
      } else {
        setError(errorMessage(reason, "That action failed."));
      }
    } finally {
      setBusy(false);
    }
  }

  function updateCode(next: string) {
    setCode(next);
    saveDraft(draftScope, next);
    lastActivity.current = Date.now();
    if (checkpoint.current) window.clearTimeout(checkpoint.current);
    checkpoint.current = window.setTimeout(() => void saveInterviewCode(sessionId, next).catch(() => undefined), CHECKPOINT_MS);
  }

  async function runCode(kind: "run" | "submit") {
    lastActivity.current = Date.now();
    const result = await execute(kind, code);
    if (result) await refresh();
  }

  if (error && !view) return <main className="p-8"><p className="rounded-xl bg-red-50 p-4 text-red-950" role="alert">{error}</p></main>;
  if (!view || !problem) return <main className="flex items-center gap-2 p-8 text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={18} /> Loading interview…</main>;
  const finished = view.state === "COMPLETE" || view.state === "ABANDONED";

  return (
    <main className="p-3 sm:p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-green-800 hover:underline" href="/interviews"><ArrowLeft aria-hidden size={16} /> Interviews</Link>
        <div className="flex items-center gap-2">
          {offline ? <p className="flex items-center gap-1 text-sm text-amber-900" role="status"><WifiOff aria-hidden size={15} /> Reconnecting…</p> : null}
          {view.mode === "practice" && !finished ? <SolutionReveal onViewed={() => void refresh()} sessionId={sessionId} slug={view.problem_slug} /> : null}
        </div>
      </div>
      {error ? <p className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-950" role="alert">{error}</p> : null}
      <Workspace
        code={code}
        disabled={finished}
        execution={execution}
        executionError={executionError}
        onCodeChange={updateCode}
        onRun={() => void runCode("run")}
        onSubmit={() => void runCode("submit")}
        pending={pending}
        problem={problem}
        revealTopic={false}
        side={
          <InterviewerPanel
            busy={busy}
            footer={finished ? (
              <Button asChild className="w-full"><Link href={`/interviews/${sessionId}/report`}><FileText aria-hidden className="mr-2" size={16} /> {view.evaluation ? "View your report" : "Report is being prepared…"}</Link></Button>
            ) : null}
            onAdvance={(target: InterviewState) => act(() => advanceInterview(sessionId, target, view.version))}
            onHint={() => act(() => requestInterviewHint(sessionId, view.version))}
            onSend={(text) => act(() => sendInterviewMessage(sessionId, text, view.version))}
            view={view}
          />
        }
        storageId="interview"
      />
    </main>
  );
}
