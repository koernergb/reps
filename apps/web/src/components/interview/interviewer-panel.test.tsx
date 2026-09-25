import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { InterviewView } from "@/lib/api";

import { InterviewerPanel } from "./interviewer-panel";
import { MockTimer } from "./timer";

function view(overrides: Partial<InterviewView> = {}): InterviewView {
  return {
    id: "s1", problem_slug: "pair", mode: "practice", state: "APPROACH_DISCUSSION", version: 3, result: null,
    started_at: "", completed_at: null, server_now: new Date().toISOString(), deadline_at: null, time_limit_s: null,
    accommodations: {}, policy: { mode: "practice", version: "practice/v1", hint_budget: 5, max_hint_level: 5, clarification_style: "full", idle_checkin_s: 180 },
    hints_used: 1, max_hint_level: 1, current_code: "", allowed_transitions: ["CLARIFICATION", "IMPLEMENTATION"], solution_viewed: false, evaluation: null,
    transcript: [
      { sequence: 1, type: "interviewer_message", actor: "interviewer", occurred_at: "", payload: { content: "Walk me through your approach." } },
      { sequence: 2, type: "approach_proposed", actor: "learner", occurred_at: "", payload: { content: "Hash map of complements." } },
      { sequence: 3, type: "hint_given", actor: "interviewer", occurred_at: "", payload: { content: "Think about what to store.", level: 1 } },
      { sequence: 4, type: "leak_blocked", actor: "system", occurred_at: "", payload: {} },
      { sequence: 5, type: "test_failure", actor: "system", occurred_at: "", payload: { kind: "submit", verdict: "failed", visible_passed: 1, visible_total: 2, hidden_passed: 2, hidden_total: 5 } },
    ],
    ...overrides,
  };
}

describe("InterviewerPanel", () => {
  it("renders the transcript without internal events", () => {
    render(<InterviewerPanel busy={false} onAdvance={vi.fn()} onHint={vi.fn()} onSend={vi.fn()} view={view()} />);
    expect(screen.getByText("Walk me through your approach.")).toBeInTheDocument();
    expect(screen.getByText("Hash map of complements.")).toBeInTheDocument();
    expect(screen.getByText("Hint (level 1)")).toBeInTheDocument();
    expect(screen.getByText(/hidden 2\/5/)).toBeInTheDocument();
    expect(screen.queryByText(/leak/i)).not.toBeInTheDocument();
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Approach");
  });

  it("sends messages and advances only to allowed states", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const onAdvance = vi.fn().mockResolvedValue(undefined);
    render(<InterviewerPanel busy={false} onAdvance={onAdvance} onHint={vi.fn()} onSend={onSend} view={view()} />);
    fireEvent.change(screen.getByLabelText("Message the interviewer"), { target: { value: "  I'd use a dict  " } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith("I'd use a dict"));
    fireEvent.click(screen.getByRole("button", { name: /ready to code/i }));
    expect(onAdvance).toHaveBeenCalledWith("IMPLEMENTATION");
    expect(screen.queryByRole("button", { name: /complexity/i })).not.toBeInTheDocument();
  });

  it("shows remaining hints and disables when none are left", () => {
    render(<InterviewerPanel busy={false} onAdvance={vi.fn()} onHint={vi.fn()} onSend={vi.fn()} view={view({ mode: "mock", hints_used: 1, max_hint_level: 1, policy: { ...view().policy, hint_budget: 1, max_hint_level: 1 } })} />);
    expect(screen.getByRole("button", { name: /Hint \(none left\)/ })).toBeDisabled();
  });

  it("hides the composer when the interview is complete", () => {
    render(<InterviewerPanel busy={false} footer={<p>report link</p>} onAdvance={vi.fn()} onHint={vi.fn()} onSend={vi.fn()} view={view({ state: "COMPLETE", allowed_transitions: [] })} />);
    expect(screen.queryByLabelText("Message the interviewer")).not.toBeInTheDocument();
    expect(screen.getByText("report link")).toBeInTheDocument();
  });
});

describe("MockTimer", () => {
  it("counts down from the server clock, not the client clock", () => {
    const serverNow = new Date(Date.now() + 60 * 60_000).toISOString();
    const deadline = new Date(Date.now() + 70 * 60_000).toISOString();
    render(<MockTimer deadline={deadline} reduceMotion={false} serverNow={serverNow} />);
    expect(screen.getByRole("timer")).toHaveTextContent(/^\s*(9|10):\d\d/);
  });

  it("uses a calm label when motion is reduced", () => {
    const now = new Date().toISOString();
    render(<MockTimer deadline={new Date(Date.now() + 5 * 60_000).toISOString()} reduceMotion serverNow={now} />);
    expect(screen.getByRole("timer")).toHaveTextContent(/About \d+ min left/);
  });
});
