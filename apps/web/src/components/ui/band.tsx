import type { Band } from "@/lib/api";
import { cn } from "@/lib/cn";

const STYLES: Record<Band, string> = {
  Weak: "bg-red-50 text-red-900 ring-red-200",
  Developing: "bg-amber-50 text-amber-900 ring-amber-200",
  Reliable: "bg-sky-50 text-sky-900 ring-sky-200",
  Strong: "bg-green-50 text-green-900 ring-green-200",
};

export function BandBadge({ band, className }: { band: Band; className?: string }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1", STYLES[band], className)}>{band}</span>;
}

const SEVERITY: Record<string, string> = {
  high: "bg-red-50 text-red-900 ring-red-200",
  medium: "bg-amber-50 text-amber-900 ring-amber-200",
  low: "bg-stone-100 text-stone-800 ring-stone-200",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold capitalize ring-1", SEVERITY[severity] ?? SEVERITY.low)}>{severity}</span>;
}
