import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReviewItem } from "@/lib/api";

import { ReviewRunner } from "./review-runner";

const item: ReviewItem = {
  attempt_id: "a1", task: null, task_type: "explain", mode: "retrieve", status: "in_progress",
  prompt: "Why can the left edge jump forward?", kind: "text", problem_slug: null, starter_code: null,
  hints_used: 0, hints_total: 3, hints: [], result: null, interview_session_id: null,
};

afterEach(() => vi.unstubAllGlobals());

describe("ReviewRunner", () => {
  it("submits an answer with confidence and shows rebuild feedback", async () => {
    const graded: ReviewItem = {
      ...item, status: "submitted", mode: "rebuild",
      result: { correctness: 0.2, band: "missed", feedback: "Not yet.", missing_points: ["distinct"], misconceptions: [], recommended_action: "rebuild", reference_answer: "Because…", grader: "rubric/v1", rebuild: { misconception: "Left moves one step at a time.", explanation: "Explanation", confirmation_question: "Where is left after abba?" } },
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(graded), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const onChange = vi.fn();
    render(<ReviewRunner item={item} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Your answer"), { target: { value: "not sure" } });
    fireEvent.change(screen.getByLabelText(/How confident/), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /Check answer/ }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(graded));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body).toEqual({ answer: "not sure", confidence: 2 });
  });

  it("renders feedback and the confirmation step", () => {
    render(<ReviewRunner item={{ ...item, status: "submitted", result: { correctness: 0.2, band: "missed", feedback: "Not yet.", missing_points: [], misconceptions: [], recommended_action: "rebuild", reference_answer: "Ref", grader: "rubric/v1", rebuild: { misconception: "Wrong model", explanation: "Right model", confirmation_question: "Check?" } } }} onChange={vi.fn()} />);
    expect(screen.getByText("Not yet")).toBeInTheDocument();
    expect(screen.getByText(/Let's rebuild this idea/)).toBeInTheDocument();
    expect(screen.getByLabelText("Check?")).toBeInTheDocument();
    expect(screen.queryByLabelText("Your answer")).not.toBeInTheDocument();
  });
});
