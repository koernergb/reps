import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function SignInPage() {
  return <main className="grid min-h-screen place-items-center px-6"><section className="w-full max-w-md rounded-2xl border bg-white p-8 shadow-sm"><p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Reps</p><h1 className="mt-3 text-3xl font-bold">Your private study workspace</h1><p className="mt-3 leading-7 text-[var(--muted)]">Reps is intentionally a single-user app. Your courses, cards, interview history, and provider settings stay in the database on this computer. Do not expose the local services to a network.</p><Button asChild className="mt-7 w-full"><Link href="/dashboard">Continue locally</Link></Button></section></main>;
}
