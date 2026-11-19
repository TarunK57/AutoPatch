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
      className="h-14 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 flex items-center justify-between select-none sticky top-0 z-30 transition-colors"
      role="banner"
    >
      {/* Brand & Project Context */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm">
            <ShieldAlert className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-slate-900 dark:text-white text-base">
              AutoPatch
            </span>
            <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
              Verified Repair
            </span>
          </div>
        </div>

        {currentProject && (
          <div className="hidden sm:flex items-center space-x-2 pl-4 border-l border-slate-200 dark:border-slate-800 text-xs">
            <FolderGit2 className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
            <span className="font-medium text-slate-700 dark:text-slate-300">
              {currentProject.name}
            </span>
            <span className="text-slate-400">({currentProject.total_files} files)</span>
          </div>
        )}
      </div>

      {/* Center Job Progress Indicator */}
      {activeJob && activeJob.status === "RUNNING" && (
        <div
          className="flex items-center space-x-3 px-3 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800"
          role="status"
          aria-live="polite"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-600"></span>
          </span>
          <span className="text-xs font-medium text-indigo-700 dark:text-indigo-300">
            Scanning: {activeJob.completed_bugs}/{activeJob.total_bugs} bugs ({Math.round(activeJob.progress)}%)
          </span>
        </div>
      )}

      {/* Right Controls */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onOpenExport}
          className="hidden md:inline-flex items-center space-x-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-colors"
          title="Export Patches, SARIF, or Diff (E)"
          aria-label="Export project patches and reports"
        >
          <Download className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Export</span>
        </button>

        <button
          onClick={onToggleTrace}
          className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-indigo-50 dark:bg-indigo-950 hover:bg-indigo-100 dark:hover:bg-indigo-900 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 transition-colors"
          title="Toggle Live Agent Trace Panel (T)"
          aria-label="Toggle Live Agent Trace panel"
        >
          <Terminal className="w-3.5 h-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Agent Trace</span>
        </button>

        <button
          onClick={onOpenShortcuts}
          className="p-1.5 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Keyboard Shortcuts (?)"
          aria-label="Keyboard Shortcuts"
        >
          <Keyboard className="w-4 h-4" aria-hidden="true" />
        </button>

        <button
          onClick={onToggleTheme}
          className="p-1.5 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Toggle Dark / Light Theme (D)"
          aria-label="Toggle Theme"
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4" aria-hidden="true" />
          ) : (
            <Moon className="w-4 h-4" aria-hidden="true" />
          )}
        </button>
      </div>
    </header>
  );
};
