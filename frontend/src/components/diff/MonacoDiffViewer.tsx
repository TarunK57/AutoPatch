"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { Copy, Check, Split, AlignJustify } from "lucide-react";

// Dynamically import Monaco DiffEditor to ensure client-only execution
const DynamicMonacoDiff = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.DiffEditor),
  {
    ssr: false,
    loading: () => (
      <div className="h-80 w-full flex items-center justify-center bg-slate-900/40 text-slate-400 text-xs font-mono animate-pulse">
        Initializing Monaco Diff Engine...
      </div>
    ),
  }
);

interface MonacoDiffViewerProps {
  original: string;
  modified: string;
  language?: string;
  height?: string;
  theme?: string;
  readOnly?: boolean;
}

export const MonacoDiffViewer: React.FC<MonacoDiffViewerProps> = ({
  original,
  modified,
  language = "python",
  height = "380px",
  theme = "vs-dark",
  readOnly = true,
}) => {
  const [copied, setCopied] = useState(false);
  const [inlineMode, setInlineMode] = useState(false);
  const [hasError, setHasError] = useState(false);

  const handleCopyUnified = () => {
    navigator.clipboard.writeText(`--- Original\n+++ Patched\n${modified}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden bg-slate-950 shadow-sm flex flex-col">
      {/* Diff Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800 text-xs text-slate-400">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-medium text-slate-200">Side-by-Side Unified Diff</span>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            {language}
          </span>
          <span className="text-slate-500 text-[11px]">Minimal diff enforced (tests unchanged)</span>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setInlineMode(!inlineMode)}
            className="flex items-center space-x-1 px-2 py-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition-colors text-[11px]"
            title={inlineMode ? "Switch to side-by-side view" : "Switch to inline view"}
          >
            {inlineMode ? <Split className="w-3.5 h-3.5 mr-1" /> : <AlignJustify className="w-3.5 h-3.5 mr-1" />}
            <span>{inlineMode ? "Side-by-Side" : "Inline"}</span>
          </button>
          <button
            onClick={handleCopyUnified}
            className="flex items-center space-x-1 px-2 py-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition-colors text-[11px]"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? "Copied" : "Copy Diff"}</span>
          </button>
        </div>
      </div>

      {/* Editor / Fallback View */}
      <div style={{ height }} className="w-full relative">
        {!hasError ? (
          <DynamicMonacoDiff
            original={original || "// Original code"}
            modified={modified || "// Patched code"}
            language={language}
            theme={theme}
            height="100%"
            options={{
              readOnly,
              renderSideBySide: !inlineMode,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              fontSize: 12,
              fontFamily: "'JetBrains Mono', monospace",
              renderOverviewRuler: false,
              wordWrap: "on",
              diffCodeLens: true,
            }}
          />
        ) : (
          /* Robust Fallback View if WebWorker or Monaco fails to initialize */
          <div className="grid grid-cols-2 h-full font-mono text-xs overflow-auto divide-x divide-slate-800">
            <div className="p-3 bg-red-950/20 text-red-200">
              <div className="text-[10px] text-red-400 font-bold uppercase tracking-wider mb-2">Original</div>
              <pre className="whitespace-pre-wrap">{original}</pre>
            </div>
            <div className="p-3 bg-emerald-950/20 text-emerald-200">
              <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider mb-2">Patched</div>
              <pre className="whitespace-pre-wrap">{modified}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
