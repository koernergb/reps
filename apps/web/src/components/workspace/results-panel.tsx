import { CheckCircle2, CircleAlert, LoaderCircle, XCircle } from "lucide-react";

import type { Execution, VisibleTestResult } from "@/lib/api";

const STATUS_LABEL: Record<VisibleTestResult["status"], string> = {
  passed: "Passed",
  wrong_answer: "Wrong answer",
  error: "Error",
  timeout: "Timed out",
  memory_limit: "Memory limit",
  output_limit: "Output limit",
  crashed: "Crashed",
  not_run: "Not run",
};

const FAILURE_LABEL: Record<string, string> = {
  wrong_answer: "wrong answer",
  error: "runtime error",
  timeout: "time limit (check your complexity)",
  memory_limit: "memory limit",
  output_limit: "output limit",
  crashed: "crash",
  not_run: "not run",
};

function show(value: unknown): string {
  const text = JSON.stringify(value);
  return text && text.length > 300 ? `${text.slice(0, 297)}…` : (text ?? "null");
}

export function ResultsPanel({ execution, error, pending }: { execution: Execution | null; error: string | null; pending: "run" | "submit" | null }) {
  const result = execution?.result;
  return (
    <section aria-live="polite" aria-label="Test results" className="h-full overflow-auto bg-white p-4 text-sm">
      {pending ? (
        <p className="flex items-center gap-2 text-[var(--muted)]">
          <LoaderCircle aria-hidden className="animate-spin" size={16} /> {pending === "run" ? "Running visible tests…" : "Submitting against all tests…"}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-950" role="alert">
          {error}
        </p>
      ) : null}
      {!pending && !error && !result ? <p className="text-[var(--muted)]">Run visible tests with ⌘/Ctrl + Enter. Submit against hidden tests with ⌘/Ctrl + Shift + Enter.</p> : null}
      {result && !pending ? (
        <div>
          <p className="flex items-center gap-2 font-bold">
            {result.verdict === "passed" ? <CheckCircle2 aria-hidden className="text-green-700" size={18} /> : result.verdict ? <XCircle aria-hidden className="text-red-700" size={18} /> : <CircleAlert aria-hidden className="text-amber-700" size={18} />}
            {execution?.kind === "submit" ? "Submission" : "Run"}: {result.message}
          </p>
          {result.hidden ? (
            <p className="mt-2 rounded-lg bg-stone-100 px-3 py-2">
              Hidden tests: {result.hidden.passed} / {result.hidden.total} passed
              {Object.keys(result.hidden.failures).length ? (
                <span className="text-[var(--muted)]"> — failures: {Object.entries(result.hidden.failures).map(([kind, count]) => `${count} ${FAILURE_LABEL[kind] ?? kind}`).join(", ")}</span>
              ) : null}
            </p>
          ) : null}
          <ol className="mt-3 space-y-2">
            {(result.visible ?? []).map((test, index) => (
              <li className="rounded-lg border p-3" key={test.id}>
                <p className={test.status === "passed" ? "font-semibold text-green-800" : "font-semibold text-red-800"}>
                  Test {index + 1}: {STATUS_LABEL[test.status]}
                  {test.duration_ms != null ? <span className="ml-2 font-normal text-[var(--muted)]">{test.duration_ms} ms</span> : null}
                </p>
                <dl className="mt-1 grid grid-cols-[5rem_1fr] gap-x-2 font-mono text-xs">
                  <dt className="text-[var(--muted)]">input</dt>
                  <dd className="break-all">{show(test.args)}</dd>
                  <dt className="text-[var(--muted)]">expected</dt>
                  <dd className="break-all">{show(test.expected)}</dd>
                  {test.status !== "not_run" ? (
                    <>
                      <dt className="text-[var(--muted)]">actual</dt>
                      <dd className="break-all">{test.error ? test.error : show(test.actual)}</dd>
                    </>
                  ) : null}
                  {test.stdout ? (
                    <>
                      <dt className="text-[var(--muted)]">stdout</dt>
                      <dd className="whitespace-pre-wrap break-all">{test.stdout}</dd>
                    </>
                  ) : null}
                </dl>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
