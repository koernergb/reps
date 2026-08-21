import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function SignInPage() {
  return <main className="grid min-h-screen place-items-center px-6"><section className="w-full max-w-md rounded-2xl border bg-white p-8 shadow-sm"><p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">Reps</p><h1 className="mt-3 text-3xl font-bold">Sign in</h1><p className="mt-3 leading-7 text-[var(--muted)]">Authentication is intentionally deferred until its architecture and privacy behavior pass Human Gate 0.</p><Button asChild className="mt-7 w-full" variant="secondary"><Link href="/">Return home</Link></Button></section></main>;
}
