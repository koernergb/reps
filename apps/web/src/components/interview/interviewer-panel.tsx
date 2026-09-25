"use client";

import { ArrowRight, Flag, Lightbulb, LoaderCircle, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import type { InterviewState, InterviewView, TranscriptEvent } from "@/lib/api";

import { MockTimer } from "./timer";
import { STATE_LABELS, StateStepper } from "./state-stepper";

const NEXT_LABEL: Partial<Record<InterviewState, string>> = {
  CLARIFICATION: "Ask clarifying questions",
  APPROACH_DISCUSSION: "Discuss my approach",
  IMPLEMENTATION: "I'm ready to code",
  TESTING: "Move to testing",
  COMPLEXITY: "Discuss complexity",
  FOLLOW_UP: "Follow-up questions",
};

function line(event: TranscriptEvent): { who: string; text: string; tone: string } | null {
  const content = typeof event.payload.content === "string" ? event.payload.content : "";
  switch (event.type) {
    case "interviewer_message":
      return { who: "Interviewer", text: content, tone: "bg-stone-100" };
    case "hint_given":
      return { who: `Hint (level ${String(event.payload.level)})`, text: content, tone: "bg-amber-50 ring-1 ring-amber-200" };
    case "state_changed":
      return { who: "", text: `— ${STATE_LABELS[event.payload.to_state as InterviewState] ?? String(event.payload.to_state)} —`, tone: "text-center text-xs text-[var(--muted)]" };
    case "run_tests":
    case "solution_submitted":
      return null;
    case "test_success":
    case "test_failure": {
      const payload = event.payload as Record<string, number | string | null>;
      const hidden = payload.hidden_total != null ? `, hidden ${payload.hidden_passed}/${payload.hidden_total}` : "";
      return { who: event.payload.kind === "submit" ? "Submission" : "Run", text: `${String(payload.verdict)} (visible ${payload.visible_passed}/${payload.visible_total}${hidden})`, tone: event.type === "test_success" ? "bg-green-50 text-green-950" : "bg-red-50 text-red-950" };
    }
    case "timer_expired":
      return { who: "", text: "Time is up.", tone: "text-center text-xs font-semibold text-red-800" };
    case "solution_viewed":
      return { who: "", text: "Solution viewed — this attempt now counts as assisted.", tone: "text-center text-xs text-amber-900" };
    case "leak_blocked":
      return null;
    default:
      return content ? { who: "You", text: content, tone: "bg-green-800 text-white ml-6" } : null;
  }
}

type Props = {
  view: InterviewView;
  busy: boolean;
  onSend: (text: string) => Promise<void>;
  onAdvance: (target: InterviewState) => Promise<void>;
  onHint: () => Promise<void>;
  footer?: React.ReactNode;
};

export function InterviewerPanel({ view, busy, onSend, onAdvance, onHint, footer }: Props) {
  const [draft, setDraft] = useState("");
  const [confirmHint, setConfirmHint] = useState(false);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const finished = view.state === "COMPLETE" || view.state === "ABANDONED";
  const hintsLeft = Math.max(0, Math.min(view.policy.hint_budget - view.hints_used, view.policy.max_hint_level - view.max_hint_level));
  const forward = view.allowed_transitions.filter((state) => NEXT_LABEL[state]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [view.transcript.length]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    await onSend(text);
    setDraft("");
  }

  return (
    <aside aria-label="Interviewer" className="flex h-full flex-col bg-white">
      <header className="space-y-2 border-b p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-bold">{view.mode === "mock" ? "Mock interview" : "Practice interview"}</p>
          {view.deadline_at && !finished ? <MockTimer deadline={view.deadline_at} reduceMotion={Boolean(view.accommodations.reduce_motion)} serverNow={view.server_now} /> : null}
        </div>
        <StateStepper state={view.state} />
      </header>
      <div aria-live="polite" className="flex-1 space-y-2 overflow-auto p-3 text-sm">
        {view.transcript.map((event) => {
          const item = line(event);
          if (!item) return null;
          return (
            <div className={`rounded-xl px-3 py-2 leading-6 ${item.tone}`} key={event.sequence}>
              {item.who ? <p className="text-[11px] font-bold uppercase tracking-wide opacity-70">{item.who}</p> : null}
              <p className="whitespace-pre-wrap">{item.text}</p>
            </div>
          );
        })}
        {busy ? <p className="flex items-center gap-2 text-xs text-[var(--muted)]"><LoaderCircle aria-hidden className="animate-spin" size={14} /> Interviewer is responding…</p> : null}
        <div ref={bottom} />
      </div>
      {!finished ? (
        <div className="space-y-2 border-t p-3">
          <form className="flex gap-2" onSubmit={submit}>
            <label className="sr-only" htmlFor="interview-message">Message the interviewer</label>
            <textarea
              className="min-h-16 flex-1 resize-y rounded-lg border px-3 py-2 text-sm focus:outline-2 focus:outline-green-700"
              disabled={busy}
              id="interview-message"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit(event);
                }
              }}
              placeholder="Think aloud, ask a question, or explain your approach…"
              value={draft}
            />
            <Button aria-label="Send message" disabled={busy || !draft.trim()} type="submit"><Send aria-hidden size={16} /></Button>
          </form>
          <div className="flex flex-wrap gap-2">
            {forward.map((state) => (
              <Button disabled={busy} key={state} onClick={() => void onAdvance(state)} variant="secondary">{NEXT_LABEL[state]} <ArrowRight aria-hidden className="ml-1" size={14} /></Button>
            ))}
            <Button disabled={busy || hintsLeft === 0} onClick={() => setConfirmHint(true)} variant="ghost">
              <Lightbulb aria-hidden className="mr-1" size={15} /> Hint {hintsLeft === 0 ? "(none left)" : `(${hintsLeft} left)`}
            </Button>
            <Button disabled={busy} onClick={() => setConfirmEnd(true)} variant="ghost"><Flag aria-hidden className="mr-1" size={15} /> End</Button>
          </div>
          {footer}
        </div>
      ) : (
        <div className="border-t p-3">{footer}</div>
      )}
      <ConfirmDialog confirmLabel="Get a hint" onCancel={() => setConfirmHint(false)} onConfirm={() => { setConfirmHint(false); void onHint(); }} open={confirmHint} title="Use a hint?">
        <p>Hints are recorded as evidence and reduce how much this attempt counts toward independent mastery. {view.mode === "mock" ? "Mock mode allows one small nudge." : `Hints get progressively more specific (level ${view.max_hint_level + 1} of 5 next).`}</p>
      </ConfirmDialog>
      <ConfirmDialog confirmLabel="End interview" onCancel={() => setConfirmEnd(false)} onConfirm={() => { setConfirmEnd(false); void onAdvance("COMPLETE"); }} open={confirmEnd} title="End the interview now?">
        <p>Your report will be based on what happened so far, including any failed submissions.</p>
      </ConfirmDialog>
    </aside>
  );
}
