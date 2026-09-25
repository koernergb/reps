import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Reps — Adaptive interview practice",
  description: "Practice, diagnose, and revisit technical interview skills.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
