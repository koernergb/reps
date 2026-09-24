"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { createExecution, errorMessage, getExecution, newKey, type Execution } from "@/lib/api";

const TERMINAL = new Set(["completed", "failed", "cancelled", "expired"]);
const POLL_MS = 400;
const MAX_POLL_MS = 60_000;

export function useExecution(problemSlug: string, sessionId?: string) {
  const [execution, setExecution] = useState<Execution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<"run" | "submit" | null>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const execute = useCallback(
    async (kind: "run" | "submit", code: string): Promise<Execution | null> => {
      setPending(kind);
      setError(null);
      try {
        let current = await createExecution({ problem_slug: problemSlug, code, kind, idempotency_key: newKey(), session_id: sessionId });
        setExecution(current);
        const started = Date.now();
        while (!TERMINAL.has(current.status) && !cancelled.current) {
          if (Date.now() - started > MAX_POLL_MS) {
            setError("Execution is taking longer than expected. Is the execution worker running (`pnpm dev:worker`)?");
            return current;
          }
          await new Promise((resolve) => setTimeout(resolve, POLL_MS));
          current = await getExecution(current.id);
          if (!cancelled.current) setExecution(current);
        }
        return current;
      } catch (reason) {
        setError(errorMessage(reason, "Execution failed."));
        return null;
      } finally {
        if (!cancelled.current) setPending(null);
      }
    },
    [problemSlug, sessionId],
  );

  return { execution, error, pending, execute };
}
