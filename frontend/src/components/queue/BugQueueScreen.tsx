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
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");

  // Filtering
  const filteredBugs = useMemo(() => {
    return bugs.filter((b) => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchesDesc = b.description.toLowerCase().includes(q);
        const matchesFile = b.file_path.toLowerCase().includes(q);
        const matchesSymbol = b.symbol?.toLowerCase().includes(q);
        if (!matchesDesc && !matchesFile && !matchesSymbol) return false;
      }
      if (selectedSeverity !== "ALL" && b.severity_level !== selectedSeverity) {
        return false;
      }
      if (selectedCategory !== "ALL" && b.category !== selectedCategory) {
        return false;
      }
      if (verifiedOnly && b.status !== "VERIFIED") {
        return false;
      }
      if (selectedStatus !== "ALL" && b.status !== selectedStatus) {
        return false;
      }
      return true;
    });
  }, [bugs, searchQuery, selectedSeverity, selectedCategory, verifiedOnly, selectedStatus]);

  const getSeverityBadge = (level: SeverityLevel) => {
    switch (level) {
      case "CRITICAL":
        return "bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border-red-200 dark:border-red-900";
      case "HIGH":
        return "bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-900";
      case "MEDIUM":
        return "bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-900";
      default:
        return "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700";
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-6 px-4 sm:px-6 space-y-5">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800 gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            Prioritized Bug Queue
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Ranked deterministically by Priority = Severity × Confidence × Impact
          </p>
        </div>

        <div className="text-xs text-slate-400 flex items-center space-x-2">
          <span>Showing {filteredBugs.length} of {bugs.length} flaws</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by description, file path, symbol..."
              className="w-full text-xs pl-8 pr-3 py-1.5 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
            />
          </div>

          {/* Severity Filter */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200"
          >
            <option value="ALL">All Categories</option>
            <option value="security">Security</option>
            <option value="crash">Crash</option>
            <option value="data_loss">Data Loss</option>
            <option value="wrong_output">Wrong Output</option>
            <option value="style">Style</option>
          </select>

          {/* Verified Only Toggle */}
          <label className="flex items-center space-x-2 text-xs font-medium text-slate-700 dark:text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={verifiedOnly}
              onChange={(e) => setVerifiedOnly(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
            />
            <span className="flex items-center space-x-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              <span>Verified Fixes Only</span>
            </span>
          </label>
        </div>
      </div>

      {/* Bug Table */}
      {filteredBugs.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-slate-300 dark:border-slate-800 rounded-lg bg-white dark:bg-slate-900">
          <CheckCircle2 className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">No matching flaws found</h3>
          <p className="text-xs text-slate-400 mt-1">Try resetting search filters or scanning another branch.</p>
        </div>
      ) : (
        <div className="border border-slate-200 dark:border-slate-800 rounded-lg bg-white dark:bg-slate-900 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" role="table">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider select-none">
                <tr>
                  <th scope="col" className="py-2.5 px-3 w-12 text-center">Rank</th>
                  <th scope="col" className="py-2.5 px-3">Flaw & Description</th>
                  <th scope="col" className="py-2.5 px-3">Location</th>
                  <th scope="col" className="py-2.5 px-3">Severity</th>
                  <th scope="col" className="py-2.5 px-3">Confidence</th>
                  <th scope="col" className="py-2.5 px-3">Status</th>
                  <th scope="col" className="py-2.5 px-3 text-right">Priority</th>
                  <th scope="col" className="py-2.5 px-2 w-8"><span className="sr-only">Action</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredBugs.map((bug) => {
                  const isSelected = bug.bug_id === selectedBugId;
                  const isApproved = bug.decision?.status === "APPROVED" || bug.is_patch_applied;
                  const isRejected = bug.decision?.status === "REJECTED";

                  return (
                    <tr
                      key={bug.bug_id}
                      onClick={() => onSelectBug(bug)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-indigo-50/70 dark:bg-indigo-950/40 font-medium"
                          : "hover:bg-slate-50 dark:hover:bg-slate-800/40"
                      }`}
                      role="row"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") onSelectBug(bug);
                      }}
                    >
                      {/* Rank */}
                      <td className="py-3 px-3 font-bold text-slate-400 text-center">
                        #{bug.rank}
                      </td>

                      {/* Description */}
                      <td className="py-3 px-3 max-w-md">
                        <div className="flex items-center space-x-1.5">
                          {isApproved && (
                            <span className="p-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" title="Approved by human">
                              <Check className="w-3 h-3" />
                            </span>
                          )}
                          {isRejected && (
                            <span className="p-0.5 rounded bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300" title="Rejected by human">
                              <X className="w-3 h-3" />
                            </span>
                          )}
                          <p className="font-semibold text-slate-900 dark:text-white truncate">
                            {bug.description}
                          </p>
                        </div>
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                          {bug.category}
                        </span>
                      </td>

                      {/* Location */}
                      <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                        {bug.file_path}:{bug.line_start}
                      </td>

                      {/* Severity */}
                      <td className="py-3 px-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${getSeverityBadge(
                            bug.severity_level
                          )}`}
                        >
                          {bug.severity_level}
                        </span>
                      </td>

                      {/* Confidence */}
                      <td className="py-3 px-3 font-semibold text-slate-700 dark:text-slate-300">
                        {(bug.confidence * 100).toFixed(0)}%
                      </td>

                      {/* Verification Status */}
                      <td className="py-3 px-3">
                        {bug.status === "VERIFIED" ? (
                          <span className="inline-flex items-center space-x-1 text-emerald-600 dark:text-emerald-400 font-bold text-[10px] uppercase">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>VERIFIED</span>
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[10px] uppercase font-medium">
                            {bug.status.replace(/_/g, " ")}
                          </span>
                        )}
                      </td>

                      {/* Priority Score */}
                      <td className="py-3 px-3 text-right">
                        <span className="text-xs font-black text-indigo-600 dark:text-indigo-400">
                          {bug.priority_score.toFixed(1)}
                        </span>
                        <span className="text-[10px] text-slate-400">/100</span>
                      </td>

                      {/* Arrow */}
                      <td className="py-3 px-2 text-slate-300 dark:text-slate-700">
                        <ChevronRight className="w-4 h-4" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
