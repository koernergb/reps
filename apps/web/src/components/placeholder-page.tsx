import { Construction } from "lucide-react";

export function PlaceholderPage({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">{eyebrow}</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">{title}</h1>
      <div className="mt-10 rounded-2xl border border-dashed bg-white/70 p-8 sm:p-12">
        <Construction aria-hidden className="text-green-800" />
        <p className="mt-4 max-w-xl text-lg leading-8 text-[var(--muted)]">{description}</p>
        <p className="mt-4 text-sm font-semibold">This route is established in Milestone 0; behavior arrives in its named milestone.</p>
      </div>
    </div>
  );
}
