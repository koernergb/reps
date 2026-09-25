"use client";

import { Clock } from "lucide-react";
import { useEffect, useState } from "react";

// The server owns the deadline. We compute a clock offset from `serverNow` so a wrong or
// changed client clock cannot extend the time contract; expiry is enforced server-side.
export function MockTimer({ deadline, serverNow, reduceMotion }: { deadline: string; serverNow: string; reduceMotion: boolean }) {
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    const offset = new Date(serverNow).getTime() - Date.now();
    const target = new Date(deadline).getTime();
    const tick = () => setRemaining(Math.max(0, target - (Date.now() + offset)));
    tick();
    const interval = window.setInterval(tick, reduceMotion ? 30_000 : 1000);
    return () => window.clearInterval(interval);
  }, [deadline, serverNow, reduceMotion]);
  const minutes = Math.floor(remaining / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1000);
  const low = remaining < 5 * 60_000;
  const label = reduceMotion ? `About ${Math.max(1, Math.ceil(remaining / 60_000))} min left` : `${minutes}:${seconds.toString().padStart(2, "0")}`;
  return (
    <p aria-label={`Time remaining: ${minutes} minutes`} className={low ? "flex items-center gap-1 font-mono text-sm font-bold text-red-800" : "flex items-center gap-1 font-mono text-sm font-semibold"} role="timer">
      <Clock aria-hidden size={14} /> {label}
    </p>
  );
}
