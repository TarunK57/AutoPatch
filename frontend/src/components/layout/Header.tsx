"use client";

import React from "react";
import {
  ShieldAlert,
  Moon,
  Sun,
  Activity,
  Terminal,
  Keyboard,
  Download,
  FolderGit2,
  GitBranch,
  Search,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Layers,
} from "lucide-react";
import { Project, ScanJob } from "@/types";

interface HeaderProps {
  currentProject: Project | null;
  activeJob: ScanJob | null;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onToggleTrace: () => void;
  onOpenShortcuts: () => void;
  onOpenExport: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentProject,
  activeJob,
  theme,
  onToggleTheme,
  onToggleTrace,
  onOpenShortcuts,
  onOpenExport,
}) => {
  return (
    <header
      className="h-14 border-b border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-bg px-4 flex items-center justify-between select-none sticky top-0 z-30 transition-colors"
      role="banner"
    >
      {/* Sentry-Style Left: Org & Project Context */}
      <div className="flex items-center space-x-3">
        {/* Sentry-style Brand Logo */}
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-indigo-700 flex items-center justify-center text-white shadow-sm ring-1 ring-purple-400/20">
            <ShieldAlert className="w-4 h-4" aria-hidden="true" />
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="font-bold tracking-tight text-slate-900 dark:text-white text-sm font-sans">
              AutoPatch
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 font-semibold">
              v1.0
            </span>
          </div>
        </div>

        {/* Sentry Breadcrumb Divider */}
        <span className="text-slate-300 dark:text-slate-700 font-light text-sm">/</span>

        {/* Project Selector Badge */}
        {currentProject ? (
          <div className="flex items-center space-x-2 text-xs">
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-sentry-card border border-slate-200 dark:border-sentry-border text-slate-800 dark:text-slate-200 hover:border-purple-500/40 transition-colors cursor-pointer">
              <FolderGit2 className="w-3.5 h-3.5 text-purple-500" />
              <span className="font-semibold text-xs tracking-tight">{currentProject.name}</span>
            </div>

            <div className="hidden lg:flex items-center space-x-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
              <GitBranch className="w-3 h-3 text-slate-400" />
              <span>main</span>
            </div>

            {/* Environment Badge */}
            <div className="hidden sm:inline-flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>production</span>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-400">No Project Ingested</div>
        )}
      </div>

      {/* Sentry-Style Center: Active Scan Job Status */}
      <div className="hidden md:flex items-center">
        {activeJob && activeJob.status === "RUNNING" ? (
          <div
            className="flex items-center space-x-3 px-3 py-1.5 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-600 dark:text-purple-300 shadow-sm"
            role="status"
            aria-live="polite"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-600"></span>
            </span>
            <span className="text-xs font-semibold font-mono tracking-tight">
              Investigating Defects: {activeJob.completed_bugs}/{activeJob.total_bugs} ({Math.round(activeJob.progress)}%)
            </span>
            {activeJob.token_metrics && (
              <span className="text-[10px] text-purple-400 font-mono border-l border-purple-500/30 pl-2">
                ${activeJob.token_metrics.estimated_cost_usd.toFixed(4)}
              </span>
            )}
          </div>
        ) : (
          <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Zero-Regression Verification Active</span>
          </div>
        )}
      </div>

      {/* Sentry-Style Right: Action Buttons & Developer Controls */}
      <div className="flex items-center space-x-2">
        {/* Export Dossier Button */}
        <button
          onClick={onOpenExport}
          className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 text-xs font-semibold rounded-md bg-slate-100 dark:bg-sentry-card hover:bg-slate-200 dark:hover:bg-sentry-cardHover border border-slate-200 dark:border-sentry-border text-slate-700 dark:text-slate-200 transition-colors shadow-2xs"
          title="Export Patches, SARIF, or HTML Report (E)"
        >
          <Download className="w-3.5 h-3.5 text-purple-500" />
          <span className="hidden sm:inline">Export Dossier</span>
        </button>

        {/* Live SSE Stream Button */}
        <button
          onClick={onToggleTrace}
          className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 text-xs font-semibold rounded-md bg-purple-50 dark:bg-purple-950/40 hover:bg-purple-100 dark:hover:bg-purple-900/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60 transition-colors shadow-2xs"
          title="Toggle Live Agent Trace Stream (T)"
        >
          <Terminal className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Live Stream</span>
        </button>

        {/* Keyboard Shortcuts Trigger */}
        <button
          onClick={onOpenShortcuts}
          className="p-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-sentry-card rounded-md border border-transparent hover:border-slate-200 dark:hover:border-sentry-border transition-colors"
          title="Keyboard Shortcuts (?)"
          aria-label="View Keyboard Shortcuts"
        >
          <Keyboard className="w-4 h-4" />
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          className="p-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-sentry-card rounded-md border border-transparent hover:border-slate-200 dark:hover:border-sentry-border transition-colors"
          title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode (D)`}
          aria-label="Toggle Dark and Light Mode"
        >
          {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-600" />}
        </button>

        {/* User / Sentry Avatar */}
        <div className="pl-1 border-l border-slate-200 dark:border-sentry-border">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center text-[10px] font-bold text-white shadow-xs">
            AP
          </div>
        </div>
      </div>
    </header>
  );
};
