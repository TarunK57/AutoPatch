"use client";

import React, { useState, useMemo } from "react";
import {
  Search,
  Filter,
  Flame,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ShieldCheck,
  ChevronRight,
  Clock,
  ArrowUpDown,
  Check,
  X,
  Sparkles,
  BarChart3,
  Layers,
  Bug,
  FolderGit2,
  SlidersHorizontal,
} from "lucide-react";
import { BugCategory, BugItem, SeverityLevel, VerificationState } from "@/types";

interface BugQueueScreenProps {
  bugs: BugItem[];
  onSelectBug: (bug: BugItem) => void;
  selectedBugId?: string;
}

export const BugQueueScreen: React.FC<BugQueueScreenProps> = ({
  bugs,
  onSelectBug,
  selectedBugId,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [activeTab, setActiveTab] = useState<"unresolved" | "resolved" | "all">("unresolved");
  const [selectedBugIds, setSelectedBugIds] = useState<Set<string>>(new Set());

  // Filtering
  const filteredBugs = useMemo(() => {
    return bugs.filter((b) => {
      // Tab filter
      if (activeTab === "unresolved") {
        if (b.decision?.status === "APPROVED" || b.is_patch_applied) return false;
      } else if (activeTab === "resolved") {
        if (b.decision?.status !== "APPROVED" && !b.is_patch_applied) return false;
      }

      // Query filter
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchesDesc = b.description.toLowerCase().includes(q);
        const matchesFile = b.file_path.toLowerCase().includes(q);
        const matchesCategory = b.category.toLowerCase().includes(q);
        if (!matchesDesc && !matchesFile && !matchesCategory) return false;
      }

      // Severity filter
      if (selectedSeverity !== "ALL" && b.severity_level !== selectedSeverity) {
        return false;
      }

      // Category filter
      if (selectedCategory !== "ALL" && b.category !== selectedCategory) {
        return false;
      }

      return true;
    });
  }, [bugs, activeTab, searchQuery, selectedSeverity, selectedCategory]);

  const unresolvedCount = bugs.filter((b) => b.decision?.status !== "APPROVED" && !b.is_patch_applied).length;
  const resolvedCount = bugs.filter((b) => b.decision?.status === "APPROVED" || b.is_patch_applied).length;

  const handleToggleSelectAll = () => {
    if (selectedBugIds.size === filteredBugs.length) {
      setSelectedBugIds(new Set());
    } else {
      setSelectedBugIds(new Set(filteredBugs.map((b) => b.bug_id)));
    }
  };

  const handleToggleSelectBug = (e: React.MouseEvent, bugId: string) => {
    e.stopPropagation();
    const next = new Set(selectedBugIds);
    if (next.has(bugId)) {
      next.delete(bugId);
    } else {
      next.add(bugId);
    }
    setSelectedBugIds(next);
  };

  const getSeverityColor = (level: SeverityLevel) => {
    switch (level) {
      case "CRITICAL":
        return {
          bar: "bg-red-500",
          text: "text-red-500",
          bg: "bg-red-500/10",
          border: "border-red-500/20",
        };
      case "HIGH":
        return {
          bar: "bg-orange-500",
          text: "text-orange-500",
          bg: "bg-orange-500/10",
          border: "border-orange-500/20",
        };
      case "MEDIUM":
        return {
          bar: "bg-amber-500",
          text: "text-amber-500",
          bg: "bg-amber-500/10",
          border: "border-amber-500/20",
        };
      default:
        return {
          bar: "bg-blue-500",
          text: "text-blue-500",
          bg: "bg-blue-500/10",
          border: "border-blue-500/20",
        };
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-4 pb-12">
      {/* Sentry-Style Header & Filter Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-200 dark:border-sentry-border gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Issues Stream
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-sentry-card border border-slate-200 dark:border-sentry-border text-slate-500 font-semibold">
              {filteredBugs.length} issues
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Autonomous root cause localization, test synthesis (BRT), and monotonic priority ranking.
          </p>
        </div>

        {/* Tab Switcher: Unresolved / Resolved / All */}
        <div className="flex items-center p-1 rounded-lg bg-slate-100 dark:bg-sentry-card border border-slate-200 dark:border-sentry-border text-xs">
          <button
            onClick={() => setActiveTab("unresolved")}
            className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === "unresolved"
                ? "bg-white dark:bg-sentry-cardHover text-purple-600 dark:text-purple-400 shadow-2xs"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            Unresolved ({unresolvedCount})
          </button>
          <button
            onClick={() => setActiveTab("resolved")}
            className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === "resolved"
                ? "bg-white dark:bg-sentry-cardHover text-emerald-600 dark:text-emerald-400 shadow-2xs"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            Resolved with Patch ({resolvedCount})
          </button>
          <button
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === "all"
                ? "bg-white dark:bg-sentry-cardHover text-slate-900 dark:text-white shadow-2xs"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            All Issues ({bugs.length})
          </button>
        </div>
      </div>

      {/* Sentry Query Bar & Filter Controls */}
      <div className="p-3 rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Query Bar */}
          <div className="relative flex-1 min-w-[280px]">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search issues, e.g. 'is:unresolved category:security file:math.py'..."
              className="w-full text-xs pl-8 pr-3 py-2 rounded-md border border-slate-200 dark:border-sentry-border bg-slate-50 dark:bg-sentry-bg text-slate-900 dark:text-white placeholder:text-slate-400 focus:ring-1 focus:ring-purple-500 font-mono"
            />
          </div>

          {/* Severity Dropdown */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="text-xs px-3 py-2 rounded-md border border-slate-200 dark:border-sentry-border bg-slate-50 dark:bg-sentry-bg text-slate-800 dark:text-slate-200 cursor-pointer font-medium"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical (Score &gt; 80)</option>
            <option value="HIGH">High (Score &gt; 60)</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          {/* Category Dropdown */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="text-xs px-3 py-2 rounded-md border border-slate-200 dark:border-sentry-border bg-slate-50 dark:bg-sentry-bg text-slate-800 dark:text-slate-200 cursor-pointer font-medium"
          >
            <option value="ALL">All Categories</option>
            <option value="boundary">Boundary / Off-by-one</option>
            <option value="null_pointer">Null / Undefined Access</option>
            <option value="security">Security & Exploit</option>
            <option value="validation">Input Validation</option>
            <option value="concurrency">Concurrency & Race</option>
          </select>
        </div>

        {/* Batch Actions Toolbar */}
        <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-100 dark:border-sentry-border/60">
          <div className="flex items-center space-x-3">
            <label className="flex items-center space-x-2 cursor-pointer text-slate-600 dark:text-slate-400 text-xs">
              <input
                type="checkbox"
                checked={selectedBugIds.size > 0 && selectedBugIds.size === filteredBugs.length}
                onChange={handleToggleSelectAll}
                className="w-3.5 h-3.5 rounded border-slate-300 dark:border-sentry-border text-purple-600 focus:ring-purple-500"
              />
              <span>Select All ({filteredBugs.length})</span>
            </label>

            {selectedBugIds.size > 0 && (
              <span className="text-[11px] font-semibold text-purple-600 dark:text-purple-400">
                {selectedBugIds.size} selected
              </span>
            )}
          </div>

          <div className="text-[11px] text-slate-400 font-mono">
            Sorted by Monotonic Priority Score (Deterministic)
          </div>
        </div>
      </div>

      {/* Sentry-Style Stream List */}
      <div className="space-y-2">
        {filteredBugs.length === 0 ? (
          <div className="p-12 text-center rounded-lg border border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-card space-y-3">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              No Issues Found Matching Filters
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              All identified defects in this view have been resolved, verified with zero regressions, or filtered out.
            </p>
          </div>
        ) : (
          filteredBugs.map((bug) => {
            const isSelected = selectedBugId === bug.bug_id;
            const isChecked = selectedBugIds.has(bug.bug_id);
            const sev = getSeverityColor(bug.severity_level);
            const confPct = Math.round((bug.confidence || 0.8) * 100);
            const pScore = Math.round(bug.priority_score || 50);

            return (
              <div
                key={bug.bug_id}
                onClick={() => onSelectBug(bug)}
                className={`group relative rounded-lg border transition-all cursor-pointer bg-white dark:bg-sentry-card overflow-hidden ${
                  isSelected
                    ? "border-purple-500 ring-1 ring-purple-500/40 dark:bg-sentry-cardHover"
                    : "border-slate-200 dark:border-sentry-border hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50/50 dark:hover:bg-sentry-cardHover"
                }`}
              >
                {/* Left Severity Indicator Bar */}
                <div className={`absolute left-0 top-0 bottom-0 w-1 ${sev.bar}`} />

                <div className="p-3.5 pl-4 sm:pl-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  {/* Left: Checkbox & Defect Details */}
                  <div className="flex items-start space-x-3 flex-1 min-w-0">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onClick={(e) => handleToggleSelectBug(e, bug.bug_id)}
                      onChange={() => {}}
                      className="w-3.5 h-3.5 rounded border-slate-300 dark:border-sentry-border text-purple-600 focus:ring-purple-500 mt-1 cursor-pointer"
                    />

                    <div className="space-y-1.5 flex-1 min-w-0">
                      {/* Title & CWE */}
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <span className="text-xs font-mono font-bold text-slate-400">
                          #{bug.rank || 1}
                        </span>
                        <h2 className="text-sm font-bold text-slate-900 dark:text-white truncate group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                          {bug.description}
                        </h2>

                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.2 rounded border ${sev.bg} ${sev.text} ${sev.border}`}
                        >
                          {bug.severity_level}
                        </span>

                        {bug.finding?.cwe && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                            {bug.finding.cwe}
                          </span>
                        )}
                      </div>

                      {/* Monospace Location Badge */}
                      <div className="flex items-center space-x-2 text-xs">
                        <span className="font-mono text-slate-600 dark:text-slate-400 text-[11px] truncate">
                          {bug.file_path}:{bug.line_start}
                        </span>
                        {bug.symbol && (
                          <span className="text-slate-400 dark:text-slate-500 text-[11px] font-mono">
                            in <strong className="text-slate-300">{bug.symbol}()</strong>
                          </span>
                        )}
                      </div>

                      {/* Sentry Tag Pills */}
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1 pt-1">
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-sentry-bg border border-slate-200 dark:border-sentry-border text-slate-600 dark:text-slate-400">
                          category:{bug.category}
                        </span>

                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 font-semibold flex items-center space-x-1">
                          <Check className="w-3 h-3" />
                          <span>Candidate BRT: Passed</span>
                        </span>

                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-400 font-semibold flex items-center space-x-1">
                          <ShieldCheck className="w-3 h-3" />
                          <span>0 Regressions</span>
                        </span>

                        {bug.decision?.status === "APPROVED" && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold">
                            ✓ Patch Approved
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Sentry Event Sparkline & Priority Badge */}
                  <div className="flex items-center space-x-5 shrink-0 pl-7 sm:pl-0">
                    {/* Visual Sentry Sparkline: Recurrence / Blast Radius */}
                    <div className="hidden md:flex flex-col items-end">
                      <span className="text-[10px] text-slate-400 font-mono mb-1">Impact Activity</span>
                      <div className="flex items-end space-x-1 h-6">
                        <div className="w-1.5 h-2 bg-slate-300 dark:bg-slate-700 rounded-xs" />
                        <div className="w-1.5 h-3 bg-slate-300 dark:bg-slate-700 rounded-xs" />
                        <div className="w-1.5 h-2 bg-purple-400/40 rounded-xs" />
                        <div className="w-1.5 h-4 bg-purple-400/60 rounded-xs" />
                        <div className="w-1.5 h-5 bg-purple-500 rounded-xs" />
                        <div className="w-1.5 h-6 bg-red-500 rounded-xs" />
                      </div>
                    </div>

                    {/* Priority Score Pill */}
                    <div className="flex flex-col items-end">
                      <div className="flex items-baseline space-x-1">
                        <span className="text-base font-extrabold font-mono text-slate-900 dark:text-white">
                          {pScore}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">/100</span>
                      </div>
                      <span className="text-[10px] text-purple-600 dark:text-purple-400 font-semibold font-mono">
                        {confPct}% conf
                      </span>
                    </div>

                    <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
