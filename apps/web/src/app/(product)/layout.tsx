import { AppShell } from "@/components/app-shell";
import { LocalModeBanner } from "@/components/local-mode-banner";

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  return <AppShell><LocalModeBanner />{children}</AppShell>;
}
