import { ArrowRight, BrainCircuit, Code2, Repeat2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

const steps = [
  { icon: Code2, title: "Practice", text: "Work through a realistic technical interview." },
  { icon: BrainCircuit, title: "Diagnose", text: "Turn mistakes and hints into capability-level evidence." },
  { icon: Repeat2, title: "Revisit", text: "Train weak skills later, then prove transfer independently." },
];

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8 sm:px-10">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xl font-bold"><span className="grid size-9 place-items-center rounded-xl bg-green-800 text-white">R</span>Reps</div>
        <Button asChild variant="ghost"><Link href="/sign-in">Sign in</Link></Button>
      </header>
      <section className="grid flex-1 items-center gap-12 py-20 lg:grid-cols-[1.15fr_0.85fr]">
        <div>
          <p className="mb-5 text-sm font-bold uppercase tracking-[0.2em] text-green-800">Practice that remembers</p>
          <h1 className="max-w-3xl text-5xl font-bold leading-[1.02] tracking-[-0.045em] sm:text-7xl">Turn interview mistakes into durable skill.</h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-[var(--muted)]">Reps observes how you reason, finds the capability behind each struggle, and schedules the right follow-up until you can solve an unseen problem on your own.</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Button asChild><Link href="/dashboard">Open product shell <ArrowRight aria-hidden className="ml-2" size={17} /></Link></Button>
            <Button asChild variant="secondary"><Link href="/problems">Browse problems</Link></Button>
          </div>
        </div>
        <div className="rounded-3xl border bg-white p-5 shadow-[0_24px_80px_rgba(20,50,30,0.10)] sm:p-8">
          <p className="text-sm font-semibold text-[var(--muted)]">Your learning loop</p>
          <div className="mt-3 divide-y">
            {steps.map(({ icon: Icon, title, text }, index) => (
              <div className="grid grid-cols-[2.5rem_1fr] gap-4 py-5" key={title}>
                <div className="grid size-10 place-items-center rounded-xl bg-green-50 text-green-800"><Icon aria-hidden size={20} /></div>
                <div><p className="font-bold">{index + 1}. {title}</p><p className="mt-1 text-sm leading-6 text-[var(--muted)]">{text}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
