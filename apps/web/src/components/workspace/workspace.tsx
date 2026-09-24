"use client";

import { Play, Send } from "lucide-react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

import { Button } from "@/components/ui/button";
import type { Execution, ProblemDetail } from "@/lib/api";

import { CodeEditor } from "./code-editor";
import { ProblemStatement } from "./problem-statement";
import { ResultsPanel } from "./results-panel";

function Handle({ direction }: { direction: "horizontal" | "vertical" }) {
  return (
    <PanelResizeHandle
      className={direction === "horizontal" ? "w-1.5 bg-stone-200 transition-colors hover:bg-green-300 focus-visible:bg-green-500 data-[resize-handle-state=drag]:bg-green-500" : "h-1.5 bg-stone-200 transition-colors hover:bg-green-300 focus-visible:bg-green-500 data-[resize-handle-state=drag]:bg-green-500"}
    />
  );
}

type Props = {
  problem: ProblemDetail;
  code: string;
  onCodeChange: (code: string) => void;
  onRun: () => void;
  onSubmit: () => void;
  execution: Execution | null;
  executionError: string | null;
  pending: "run" | "submit" | null;
  side?: React.ReactNode;
  toolbar?: React.ReactNode;
  revealTopic?: boolean;
  disabled?: boolean;
  storageId: string;
};

export function Workspace({ problem, code, onCodeChange, onRun, onSubmit, execution, executionError, pending, side, toolbar, revealTopic, disabled, storageId }: Props) {
  const main = (
    <PanelGroup autoSaveId={`${storageId}:main`} direction="horizontal">
      <Panel defaultSize={36} minSize={20}>
        <ProblemStatement problem={problem} revealTopic={revealTopic} />
      </Panel>
      <Handle direction="horizontal" />
      <Panel defaultSize={64} minSize={30}>
        <PanelGroup autoSaveId={`${storageId}:editor`} direction="vertical">
          <Panel defaultSize={62} minSize={20}>
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between gap-2 border-b bg-slate-900 px-3 py-2">
                <span className="text-xs font-semibold text-slate-300">Python 3.12 · standard library</span>
                <div className="flex gap-2">
                  {toolbar}
                  <Button aria-keyshortcuts="Control+Enter" className="bg-slate-700 text-white hover:bg-slate-600" disabled={disabled || pending !== null} onClick={onRun} variant="ghost">
                    <Play aria-hidden className="mr-1.5" size={15} /> Run
                  </Button>
                  <Button aria-keyshortcuts="Control+Shift+Enter" disabled={disabled || pending !== null} onClick={onSubmit}>
                    <Send aria-hidden className="mr-1.5" size={15} /> Submit
                  </Button>
                </div>
              </div>
              <div className="min-h-0 flex-1">
                <CodeEditor label={`Python solution for ${problem.title}`} onChange={onCodeChange} onRun={onRun} onSubmit={onSubmit} value={code} />
              </div>
            </div>
          </Panel>
          <Handle direction="vertical" />
          <Panel defaultSize={38} minSize={12}>
            <ResultsPanel error={executionError} execution={execution} pending={pending} />
          </Panel>
        </PanelGroup>
      </Panel>
    </PanelGroup>
  );

  if (!side) return <div className="h-[calc(100vh-7rem)] min-h-[36rem] overflow-hidden rounded-xl border">{main}</div>;
  return (
    <div className="h-[calc(100vh-7rem)] min-h-[36rem] overflow-hidden rounded-xl border">
      <PanelGroup autoSaveId={`${storageId}:side`} direction="horizontal">
        <Panel defaultSize={70} minSize={45}>
          {main}
        </Panel>
        <Handle direction="horizontal" />
        <Panel defaultSize={30} minSize={20}>
          {side}
        </Panel>
      </PanelGroup>
    </div>
  );
}
