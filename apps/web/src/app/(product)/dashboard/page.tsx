import Link from "next/link";
import { ArrowRight, CalendarClock, Target } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Today</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Build independence, one rep at a time.</h1>
      <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--muted)]">The foundation is live. Learner-specific sessions and due work arrive after the domain, interview, and scheduler milestones.</p>
      <section className="mt-10 grid gap-5 md:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl bg-green-900 p-7 text-white">
          <Target aria-hidden />
          <h2 className="mt-8 text-2xl font-bold">Start a 10-minute drill</h2>
          <p className="mt-2 text-green-100">A focused mix based on weak capabilities and due reviews.</p>
          <Button asChild className="mt-6 bg-white text-green-950 hover:bg-green-50" variant="primary"><Link href="/drills">Preview drill route <ArrowRight aria-hidden className="ml-2" size={17} /></Link></Button>
        </div>
        <div className="rounded-2xl border bg-white p-7">
          <CalendarClock aria-hidden className="text-green-800" />
          <h2 className="mt-8 text-xl font-bold">Upcoming reviews</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">No learner evidence yet. Your first interview will create the review trail.</p>
        </div>
      </section>
    </div>
  );
}
