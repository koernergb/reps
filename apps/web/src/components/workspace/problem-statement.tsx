import type { ProblemDetail } from "@/lib/api";

// Statements use `backticks` for identifiers; render them as code without a markdown parser.
function withCode(text: string) {
  return text.split(/(`[^`]+`)/g).map((part, index) =>
    part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
      <code className="rounded bg-stone-100 px-1 py-0.5 font-mono text-[0.9em]" key={index}>{part.slice(1, -1)}</code>
    ) : (
      part
    ),
  );
}

export function ProblemStatement({ problem, revealTopic = true }: { problem: ProblemDetail; revealTopic?: boolean }) {
  return (
    <article className="h-full overflow-auto bg-white p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
        <span>{problem.difficulty}</span>
        {revealTopic && problem.topic ? (
          <>
            <span aria-hidden>·</span>
            <span>{problem.topic.name}</span>
          </>
        ) : null}
        {problem.status !== "reviewed" ? <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900" title="Not yet reviewed at Human Gate 2">Unreviewed</span> : null}
      </div>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{problem.title}</h1>
      <div className="mt-4 whitespace-pre-wrap leading-7">{withCode(problem.statement)}</div>
      <h2 className="mt-6 font-bold">Examples</h2>
      {problem.examples.map((example, index) => (
        <div className="mt-2 rounded-lg border bg-stone-50 p-3 font-mono text-xs" key={index}>
          <p>
            <span className="text-[var(--muted)]">input:</span> {Object.entries(example.input).map(([name, value]) => `${name} = ${JSON.stringify(value)}`).join(", ")}
          </p>
          <p>
            <span className="text-[var(--muted)]">output:</span> {JSON.stringify(example.output)}
          </p>
          {example.explanation ? <p className="mt-1 font-sans text-[var(--muted)]">{example.explanation}</p> : null}
        </div>
      ))}
      <h2 className="mt-6 font-bold">Constraints</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
        {problem.constraints.map((constraint) => (
          <li key={constraint}>{withCode(constraint)}</li>
        ))}
      </ul>
    </article>
  );
}
