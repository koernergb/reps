import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 leading-8">
      <h1 className="text-4xl font-bold">Local data and privacy</h1>
      <p className="mt-5 text-[var(--muted)]">Reps runs for one owner on this machine without authentication. Do not expose it to a network.</p>
      <h2 className="mt-8 text-xl font-bold">What is stored</h2>
      <p className="text-[var(--muted)]">Interviews and their events (messages, code checkpoints, test results, hints), submitted code, evaluation reports, capability evidence and skill estimates, review attempts, drills, solution views, and content-free analytics. Everything stays in the local PostgreSQL database until you export or reset it in Settings. Application logs never contain code, transcripts, or hidden tests.</p>
      <h2 className="mt-8 text-xl font-bold">What is sent to an AI provider</h2>
      <p className="text-[var(--muted)]">By default (<code>LLM_PROVIDER=offline</code>) nothing leaves your machine: the interviewer, grader, and evaluator use built-in deterministic rules. If you choose OpenAI or Google Gemini in Settings (or set <code>LLM_PROVIDER</code> in <code>.env</code>), Reps sends that provider the public problem statement and clarifications, the interview state, a bounded window of your recent messages, your current code (truncated), a summary of test results, and up to three weak skill names; for evaluation, the deterministic facts, the interview transcript, and the problem&apos;s expected complexity and common-mistake descriptions; for review grading, the question, its rubric and reference answer, and your answer. Reps never sends hidden tests, problem reference solutions, your email, or credentials. The provider&apos;s API data-retention and training policies apply to anything sent; check them before enabling. API keys you save in Settings are stored in the local database, are never shown again or logged, and are excluded from exports.</p>
      <h2 className="mt-8 text-xl font-bold">Code execution</h2>
      <p className="text-[var(--muted)]">Your code runs only in an isolated Docker container with no network access and strict resource limits.</p>
      <p className="mt-8"><Link className="font-semibold text-green-800 underline" href="/settings">Export or reset your data</Link></p>
    </main>
  );
}
