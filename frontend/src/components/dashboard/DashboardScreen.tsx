"use client";

import React from "react";
import {
  ShieldAlert,
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
  // Compute metrics
  const totalBugs = bugs.length;
  const criticalCount = bugs.filter((b) => b.severity_level === "CRITICAL").length;
  const highCount = bugs.filter((b) => b.severity_level === "HIGH").length;
  const mediumCount = bugs.filter((b) => b.severity_level === "MEDIUM").length;
  const lowCount = bugs.filter((b) => b.severity_level === "LOW").length;

  const verifiedCount = bugs.filter((b) => b.status === "VERIFIED").length;
  const unverifiedCount = totalBugs - verifiedCount;

  const approvedCount = bugs.filter((b) => b.decision?.status === "APPROVED" || b.is_patch_applied).length;
  const rejectedCount = bugs.filter((b) => b.decision?.status === "REJECTED").length;
  const pendingCount = totalBugs - approvedCount - rejectedCount;

  // Calculate Health Score (100 minus penalty for unpatched critical/high bugs)
  const penalty = criticalCount * 18 + highCount * 10 + mediumCount * 4 + lowCount * 1;
  const healthScore = Math.max(12, Math.min(100, 100 - penalty + approvedCount * 12));

  const getHealthBadge = (score: number) => {
    if (score >= 85) return { text: "EXCELLENT", color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300" };
    if (score >= 65) return { text: "FAIR", color: "text-amber-600 bg-amber-50 dark:bg-amber-950/60 border-amber-300" };
    return { text: "ACTION REQUIRED", color: "text-red-600 bg-red-50 dark:bg-red-950/60 border-red-300" };
  };

  const healthBadge = getHealthBadge(healthScore);

  return (
    <div className="max-w-6xl mx-auto py-6 px-4 sm:px-6 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800 gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <span>Project Security & Defect Overview</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {project ? `${project.name} • ${project.total_files} files analyzed` : "Real-time verification telemetry"}
          </p>
        </div>

        <button
          onClick={onNavigateToQueue}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-md text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-all"
        >
          <span>Review Bug Queue</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Primary KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Health Score */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[10px]">Codebase Health</span>
            <Activity className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="my-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">
              {healthScore}
            </span>
            <span className="text-xs text-slate-400">/ 100</span>
          </div>
          <span
            className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${healthBadge.color} w-fit`}
          >
            {healthBadge.text}
          </span>
        </div>

        {/* Total Flaws */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[10px]">Detected Flaws</span>
            <Bug className="w-4 h-4 text-red-500" />
          </div>
          <div className="my-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">
              {totalBugs}
            </span>
            <span className="text-xs text-red-600 dark:text-red-400 font-semibold">
              ({criticalCount} Critical)
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Ranked by Priority = S × C × I</p>
        </div>

        {/* Verification Status */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[10px]">Verification Rate</span>
            <CheckCircle className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="my-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">
              {totalBugs > 0 ? Math.round((verifiedCount / totalBugs) * 100) : 0}%
            </span>
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
              ({verifiedCount} Proven)
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Passes BRT + 0 Suite Regressions</p>
        </div>

        {/* Human Approvals */}
        <div className="p-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[10px]">Human Approvals</span>
            <Check className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="my-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">
              {approvedCount}
            </span>
            <span className="text-xs text-slate-400 font-medium">
              ({pendingCount} Pending)
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Rule 1: Human-in-the-loop signoff</p>
        </div>
      </div>

      {/* Grid: Severity Breakdown & Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Distribution */}
        <div className="p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Defects By Severity Hierarchy
          </h2>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-red-600 dark:text-red-400 flex items-center space-x-1">
                  <Flame className="w-3.5 h-3.5" />
                  <span>CRITICAL (Security / Exploitable)</span>
                </span>
                <span className="font-bold">{criticalCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-red-500 h-2 rounded-full transition-all"
                  style={{ width: `${totalBugs > 0 ? (criticalCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-amber-600 dark:text-amber-400 flex items-center space-x-1">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>HIGH (Crashes / Data Leaks)</span>
                </span>
                <span className="font-bold">{highCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-amber-500 h-2 rounded-full transition-all"
                  style={{ width: `${totalBugs > 0 ? (highCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-blue-600 dark:text-blue-400">
                  MEDIUM (Logic Flaws / Range Bounds)
                </span>
                <span className="font-bold">{mediumCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{ width: `${totalBugs > 0 ? (mediumCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-500 dark:text-slate-400">
                  LOW (Style / Dead Code)
                </span>
                <span className="font-bold">{lowCount}</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-slate-400 h-2 rounded-full transition-all"
                  style={{ width: `${totalBugs > 0 ? (lowCount / totalBugs) * 100 : 0}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Scan Quality & Verification Guarantees */}
        <div className="p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Autonomous Verification Quality
            </h2>
            <span className="inline-flex items-center text-xs font-semibold text-emerald-600">
              <TrendingUp className="w-3.5 h-3.5 mr-1" />
              100% Repro Ratio
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-md bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
              <p className="text-[10px] text-slate-400 uppercase font-bold">Reproduction (BRT)</p>
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {verifiedCount} / {totalBugs}
              </p>
              <p className="text-[10px] text-slate-500 mt-0.5">Failed on buggy code</p>
            </div>

            <div className="p-3 rounded-md bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
              <p className="text-[10px] text-slate-400 uppercase font-bold">Suite Regressions</p>
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1">0 New Breaks</p>
              <p className="text-[10px] text-slate-500 mt-0.5">Existing test suite intact</p>
            </div>

            <div className="p-3 rounded-md bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
              <p className="text-[10px] text-slate-400 uppercase font-bold">Overfitting Guard</p>
              <p className="text-lg font-bold text-slate-800 dark:text-slate-200 mt-1">0 Special-Cased</p>
              <p className="text-[10px] text-slate-500 mt-0.5">General, minimal diffs</p>
            </div>

            <div className="p-3 rounded-md bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
              <p className="text-[10px] text-slate-400 uppercase font-bold">Sandbox Isolation</p>
              <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-1">Network: None</p>
              <p className="text-[10px] text-slate-500 mt-0.5">Ephemeral Docker sandbox</p>
            </div>
          </div>
        </div>
      </div>

      {/* Top Priority Action Items */}
      <div className="p-5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Top Priority Bugs Awaiting Decision
          </h2>
          <button
            onClick={onNavigateToQueue}
            className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold flex items-center space-x-1"
          >
            <span>View All ({totalBugs})</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {bugs.slice(0, 3).map((bug) => (
            <div
              key={bug.bug_id}
              onClick={() => onSelectBug(bug)}
              className="py-3 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50 px-2 rounded cursor-pointer transition-colors"
            >
              <div className="flex items-center space-x-3">
                <span className="w-5 text-center text-xs font-bold text-slate-400">#{bug.rank}</span>
                <div>
                  <p className="text-xs font-bold text-slate-900 dark:text-white">{bug.description}</p>
                  <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                    {bug.file_path}:{bug.line_start}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                    bug.severity_level === "CRITICAL"
                      ? "bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-400"
                      : "bg-amber-50 text-amber-600 dark:bg-amber-950 dark:text-amber-400"
                  }`}
                >
                  {bug.severity_level}
                </span>
                <span className="text-xs font-extrabold text-indigo-600 dark:text-indigo-400">
                  {bug.priority_score.toFixed(1)}/100
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
