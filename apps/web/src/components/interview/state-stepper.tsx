import type { InterviewState } from "@/lib/api";
import { cn } from "@/lib/cn";

export const STATE_LABELS: Record<InterviewState, string> = {
  INTRO: "Intro",
  CLARIFICATION: "Clarify",
  APPROACH_DISCUSSION: "Approach",
  IMPLEMENTATION: "Implement",
  TESTING: "Test",
  COMPLEXITY: "Complexity",
  FOLLOW_UP: "Follow-up",
  COMPLETE: "Complete",
  ABANDONED: "Ended",
};
const ORDER: InterviewState[] = ["INTRO", "CLARIFICATION", "APPROACH_DISCUSSION", "IMPLEMENTATION", "TESTING", "COMPLEXITY", "FOLLOW_UP", "COMPLETE"];

export function StateStepper({ state }: { state: InterviewState }) {
  const current = ORDER.indexOf(state);
  return (
    <ol aria-label="Interview phases" className="flex flex-wrap gap-1 text-[11px] font-semibold">
      {ORDER.map((step, index) => (
        <li
          aria-current={step === state ? "step" : undefined}
          className={cn("rounded-full px-2 py-0.5", step === state ? "bg-green-800 text-white" : index < current ? "bg-green-100 text-green-900" : "bg-stone-100 text-stone-500")}
          key={step}
        >
          {STATE_LABELS[step]}
        </li>
      ))}
    </ol>
  );
}
