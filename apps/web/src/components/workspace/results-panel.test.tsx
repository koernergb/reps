import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Execution } from "@/lib/api";

import { ResultsPanel } from "./results-panel";

const base: Execution = {
  id: "job-1",
  kind: "submit",
  status: "completed",
  problem_slug: "pair",
  verdict: "failed",
  created_at: "",
  finished_at: "",
  result: {
    verdict: "failed",
    message: "3 of 4 tests passed.",
    visible: [
      { id: "v1", args: [[1, 2], 3], expected: [0, 1], actual: [0, 1], status: "passed", error: null, stdout: "", duration_ms: 1 },
      { id: "v2", args: [[3, 3], 6], expected: [0, 1], actual: null, status: "error", error: "KeyError (line 3): 6", stdout: "debug\n", duration_ms: 1 },
    ],
    hidden: { passed: 1, total: 2, failures: { timeout: 1 } },
  },
};

describe("ResultsPanel", () => {
  it("shows visible detail and only aggregate hidden feedback", () => {
    render(<ResultsPanel error={null} execution={base} pending={null} />);
    expect(screen.getByText(/Submission: 3 of 4 tests passed/)).toBeInTheDocument();
    expect(screen.getByText(/Hidden tests: 1 \/ 2 passed/)).toBeInTheDocument();
    expect(screen.getByText(/1 time limit/)).toBeInTheDocument();
    expect(screen.getByText("KeyError (line 3): 6")).toBeInTheDocument();
    expect(screen.getByText("Test 2: Error")).toBeInTheDocument();
  });

  it("announces errors", () => {
    render(<ResultsPanel error="Sandbox unavailable" execution={null} pending={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Sandbox unavailable");
  });

  it("shows progress while pending", () => {
    render(<ResultsPanel error={null} execution={null} pending="run" />);
    expect(screen.getByText(/Running visible tests/)).toBeInTheDocument();
  });
});
