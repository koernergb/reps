"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

const Monaco = dynamic(() => import("@monaco-editor/react").then((module) => module.default), {
  ssr: false,
  loading: () => <p className="p-4 text-sm text-[var(--muted)]">Loading editor…</p>,
});

type Props = {
  value: string;
  onChange: (value: string) => void;
  onRun?: () => void;
  onSubmit?: () => void;
  label: string;
};

// Monaco loads from a CDN by default. If it fails (offline), fall back to an accessible textarea
// so the learner can still write and run code.
export function CodeEditor({ value, onChange, onRun, onSubmit, label }: Props) {
  const [fallback, setFallback] = useState(false);
  const [mounted, setMounted] = useState(false);
  // Monaco commands are registered once at mount; refs keep them pointed at current handlers
  // so a keyboard run always uses the latest code.
  const runRef = useRef(onRun);
  const submitRef = useRef(onSubmit);
  useEffect(() => {
    runRef.current = onRun;
    submitRef.current = onSubmit;
  }, [onRun, onSubmit]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!mounted) setFallback(true);
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [mounted]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (event.shiftKey) onSubmit?.();
      else onRun?.();
    }
    if (event.key === "Tab" && !event.shiftKey) {
      event.preventDefault();
      const target = event.currentTarget;
      const { selectionStart, selectionEnd } = target;
      const next = `${value.slice(0, selectionStart)}    ${value.slice(selectionEnd)}`;
      onChange(next);
      requestAnimationFrame(() => target.setSelectionRange(selectionStart + 4, selectionStart + 4));
    }
  }

  if (fallback) {
    return (
      <textarea
        aria-label={label}
        className="h-full w-full resize-none bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-100 focus:outline-2 focus:outline-green-500"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        value={value}
      />
    );
  }

  return (
    <div aria-label={label} className="h-full" data-editor-ready={mounted ? "true" : "false"} role="group">
      <Monaco
        defaultLanguage="python"
        onChange={(next) => onChange(next ?? "")}
        onMount={(editor, monaco) => {
          setMounted(true);
          editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current?.());
          editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter, () => submitRef.current?.());
        }}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          tabSize: 4,
          insertSpaces: true,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          accessibilitySupport: "auto",
          tabFocusMode: false,
        }}
        theme="vs-dark"
        value={value}
      />
    </div>
  );
}
