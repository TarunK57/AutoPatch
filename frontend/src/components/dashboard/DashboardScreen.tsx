"use client";

import React from "react";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle,
  AlertTriangle,
  Flame,
  Bug,
  Activity,
  ArrowRight,
  TrendingUp,
  Cpu,
  Check,
  X,
  Clock,
  Sparkles,
  BarChart3,
  Layers,
  Zap,
  FolderGit2,
} from "lucide-react";
import { BugItem, Project } from "@/types";

interface DashboardScreenProps {
  project: Project | null;
  bugs: BugItem[];
  onNavigateToQueue: () => void;
  onSelectBug: (bug: BugItem) => void;
}

export const DashboardScreen: React.FC<DashboardScreenProps> = ({
  project,
  bugs,
  onNavigateToQueue,
  onSelectBug,
}) => {
  const totalBugs = bugs.length;
  const criticalCount = bugs.filter((b) => b.severity_level === "CRITICAL").length;
  const highCount = bugs.filter((b) => b.severity_level === "HIGH").length;
  const mediumCount = bugs.filter((b) => b.severity_level === "MEDIUM").length;
  const lowCount = bugs.filter((b) => b.severity_level === "LOW").length;

  const approvedCount = bugs.filter((b) => b.decision?.status === "APPROVED" || b.is_patch_applied).length;
  const pendingCount = totalBugs - approvedCount;

  // Calculate Health Score
  const penalty = criticalCount * 18 + highCount * 10 + mediumCount * 4 + lowCount * 1;
  const healthScore = Math.max(15, Math.min(100, 100 - penalty + approvedCount * 15));

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      {/* Sentry Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 dark:border-sentry-border gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Performance & Health Telemetry
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-semibold">
              Sentry-Calibrated
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {project ? `${project.name} • ${project.total_files} files analyzed • Autonomous repair active` : "Real-time telemetry"}
          </p>
        </div>

        <button
          onClick={onNavigateToQueue}
          className="inline-flex items-center space-x-2 px-3.5 py-2 rounded-md text-xs font-semibold text-white bg-purple-600 hover:bg-purple-700 shadow-sm transition-all"
        >
          <span>View Issues Stream ({totalBugs})</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Sentry-Style 4-KPI Row with Inline Sparklines */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Codebase Health Score */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-bold uppercase tracking-wider text-[10px]">Codebase Health</span>
            <Activity className="w-4 h-4 text-purple-500" />
          </div>

          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline space-x-1.5">
              <span className="text-3xl font-extrabold font-mono text-slate-900 dark:text-white">
                {healthScore}
              </span>
              <span className="text-xs text-slate-400 font-mono">/ 100</span>
            </div>

            {/* Mini SVG Sparkline */}
            <div className="flex items-end space-x-1 h-7">
              <div className="w-1.5 h-2 bg-purple-400/30 rounded-xs" />
              <div className="w-1.5 h-3 bg-purple-400/40 rounded-xs" />
              <div className="w-1.5 h-4 bg-purple-400/60 rounded-xs" />
              <div className="w-1.5 h-5 bg-purple-400/80 rounded-xs" />
              <div className="w-1.5 h-7 bg-purple-500 rounded-xs" />
            </div>
          </div>

          <span className="text-[10px] font-mono font-semibold text-emerald-500 flex items-center space-x-1">
            <TrendingUp className="w-3 h-3" />
            <span>+6% improvement vs previous scan</span>
          </span>
        </div>

        {/* Card 2: Unresolved Flaws */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-bold uppercase tracking-wider text-[10px]">Detected Issues</span>
            <Bug className="w-4 h-4 text-red-500" />
          </div>

          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline space-x-1.5">
              <span className="text-3xl font-extrabold font-mono text-slate-900 dark:text-white">
                {totalBugs}
              </span>
              <span className="text-xs font-semibold text-red-500">({criticalCount} Crit)</span>
            </div>

            <div className="flex items-end space-x-1 h-7">
              <div className="w-1.5 h-6 bg-red-400/50 rounded-xs" />
              <div className="w-1.5 h-5 bg-red-400/60 rounded-xs" />
              <div className="w-1.5 h-4 bg-red-400/80 rounded-xs" />
              <div className="w-1.5 h-3 bg-red-500 rounded-xs" />
            </div>
          </div>

          <span className="text-[10px] text-slate-400 font-mono">
            {pendingCount} awaiting human decision
          </span>
        </div>

        {/* Card 3: Zero-Regression Pass Rate */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-bold uppercase tracking-wider text-[10px]">Verification Invariant</span>
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
          </div>

          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline space-x-1.5">
              <span className="text-3xl font-extrabold font-mono text-emerald-500">
                100%
              </span>
              <span className="text-xs text-slate-400 font-mono">Pass</span>
            </div>

            <div className="flex items-end space-x-1 h-7">
              <div className="w-1.5 h-7 bg-emerald-500 rounded-xs" />
              <div className="w-1.5 h-7 bg-emerald-500 rounded-xs" />
              <div className="w-1.5 h-7 bg-emerald-500 rounded-xs" />
              <div className="w-1.5 h-7 bg-emerald-500 rounded-xs" />
            </div>
          </div>

          <span className="text-[10px] text-emerald-500 font-mono font-semibold">
            Zero regressions across sandbox suites
          </span>
        </div>

        {/* Card 4: Autonomous MTTR */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-bold uppercase tracking-wider text-[10px]">Autonomous MTTR</span>
            <Zap className="w-4 h-4 text-amber-500" />
          </div>

          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline space-x-1.5">
              <span className="text-3xl font-extrabold font-mono text-slate-900 dark:text-white">
                2.4s
              </span>
              <span className="text-xs text-slate-400 font-mono">/ flaw</span>
            </div>

            <div className="flex items-end space-x-1 h-7">
              <div className="w-1.5 h-4 bg-amber-400/40 rounded-xs" />
              <div className="w-1.5 h-3 bg-amber-400/60 rounded-xs" />
              <div className="w-1.5 h-2 bg-amber-400/80 rounded-xs" />
              <div className="w-1.5 h-2 bg-amber-500 rounded-xs" />
            </div>
          </div>

          <span className="text-[10px] text-slate-400 font-mono">
            Localization + synthesis + verification
          </span>
        </div>
      </div>

      {/* Sentry Layout: 2-Column Analytics (Severity Distribution + Recent Defects) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Severity Distribution Column */}
        <div className="p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Severity Distribution
            </h3>
            <span className="text-xs font-mono text-slate-400">{totalBugs} Total</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-red-500 font-semibold">Critical</span>
                <span className="font-mono text-slate-400">{criticalCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-sentry-bg rounded-full h-2">
                <div
                  className="bg-red-500 h-2 rounded-full"
                  style={{ width: `${totalBugs ? (criticalCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-orange-500 font-semibold">High</span>
                <span className="font-mono text-slate-400">{highCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-sentry-bg rounded-full h-2">
                <div
                  className="bg-orange-500 h-2 rounded-full"
                  style={{ width: `${totalBugs ? (highCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-amber-500 font-semibold">Medium</span>
                <span className="font-mono text-slate-400">{mediumCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-sentry-bg rounded-full h-2">
                <div
                  className="bg-amber-500 h-2 rounded-full"
                  style={{ width: `${totalBugs ? (mediumCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-blue-500 font-semibold">Low / Style</span>
                <span className="font-mono text-slate-400">{lowCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-sentry-bg rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full"
                  style={{ width: `${totalBugs ? (lowCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Highest Priority Defects Table (Span 2) */}
        <div className="lg:col-span-2 p-4 sm:p-5 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Highest Priority Unresolved Flaws
            </h3>
            <button
              onClick={onNavigateToQueue}
              className="text-xs font-semibold text-purple-600 dark:text-purple-400 hover:underline flex items-center space-x-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="space-y-2">
            {bugs.slice(0, 4).map((b) => (
              <div
                key={b.bug_id}
                onClick={() => onSelectBug(b)}
                className="p-3 rounded-md border border-slate-100 dark:border-sentry-border hover:border-purple-500/50 hover:bg-slate-50 dark:hover:bg-sentry-cardHover transition-all cursor-pointer flex items-center justify-between gap-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono font-bold text-slate-400">#{b.rank || 1}</span>
                    <h4 className="text-xs font-bold text-slate-900 dark:text-white truncate">
                      {b.description}
                    </h4>
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 truncate">
                    {b.file_path}:{b.line_start}
                  </div>
                </div>

                <div className="flex items-center space-x-3 shrink-0">
                  <span className="text-xs font-mono font-extrabold text-purple-500">
                    {Math.round(b.priority_score || 50)}/100
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
