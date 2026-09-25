"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

type Props = {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  destructive?: boolean;
  busy?: boolean;
};

// Native <dialog> gives focus trapping, Escape handling, and inert background for free.
export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onCancel, destructive, busy }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close?.();
  }, [open]);
  return (
    <dialog aria-labelledby="dialog-title" className="w-[min(32rem,calc(100vw-2rem))] rounded-2xl border p-0 backdrop:bg-black/40" onCancel={(event) => { event.preventDefault(); onCancel(); }} ref={ref}>
      <div className="p-6">
        <h2 className="text-lg font-bold" id="dialog-title">{title}</h2>
        <div className="mt-3 text-sm leading-6 text-[var(--muted)]">{children}</div>
        <div className="mt-6 flex justify-end gap-2">
          <Button onClick={onCancel} variant="secondary">Cancel</Button>
          <Button className={destructive ? "bg-red-700 hover:bg-red-800" : undefined} disabled={busy} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </dialog>
  );
}
