import { BrainCircuit, Code2, LayoutDashboard, MessagesSquare, Repeat2, Settings, TrendingUp } from "lucide-react";
import Link from "next/link";

const navigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/drills", label: "Drills", icon: BrainCircuit },
  { href: "/reviews", label: "Reviews", icon: Repeat2 },
  { href: "/interviews", label: "Interviews", icon: MessagesSquare },
  { href: "/problems", label: "Problems", icon: Code2 },
  { href: "/history", label: "Progress", icon: TrendingUp },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
      <aside className="border-b bg-white/90 px-5 py-4 backdrop-blur lg:min-h-screen lg:border-b-0 lg:border-r lg:px-6 lg:py-7">
        <Link className="flex items-center gap-2 text-xl font-bold tracking-tight" href="/dashboard">
          <span aria-hidden className="grid size-9 place-items-center rounded-xl bg-green-800 text-white">R</span>
          Reps
        </Link>
        <nav aria-label="Primary" className="mt-5 flex gap-1 overflow-x-auto lg:mt-10 lg:flex-col">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link className="flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--muted)] hover:bg-green-50 hover:text-green-900 focus-visible:outline-2 focus-visible:outline-green-800" href={href} key={href}>
              <Icon aria-hidden size={18} />
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="px-5 py-8 sm:px-8 lg:px-12 lg:py-12">{children}</main>
    </div>
  );
}
