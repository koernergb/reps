import { HardDrive } from "lucide-react";

export function LocalModeBanner() {
  return (
    <div className="mb-7 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950" role="status">
      <HardDrive aria-hidden className="mt-0.5 shrink-0" size={17} />
      <p><strong>Local-only mode.</strong> There is no sign-in boundary. Keep the web and API bound to your machine and do not expose them through a tunnel or public network.</p>
    </div>
  );
}
