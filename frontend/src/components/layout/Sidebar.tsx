"use client";

import React from "react";
import {
  UploadCloud,
  LayoutDashboard,
  Bug,
  FileCode2,
  Terminal,
  Download,
  ShieldCheck,
  Zap,
  Activity,
  Layers,
  Sparkles,
  GitPullRequest,
} from "lucide-react";

export type NavScreen = "upload" | "dashboard" | "queue" | "bug-detail" | "trace" | "export";

interface SidebarProps {
  currentScreen: NavScreen;
  onNavigate: (screen: NavScreen) => void;
  bugsCount: number;
  hasActiveBug: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentScreen,
  onNavigate,
  bugsCount,
  hasActiveBug,
}) => {
  const navItems = [
    {
      id: "queue",
      label: "Issues Stream",
      sublabel: "Ranked bug queue",
      icon: Bug,
      badge: bugsCount > 0 ? bugsCount : undefined,
      badgeColor: "bg-red-500/10 text-red-500 border border-red-500/20",
    },
    {
      id: "dashboard",
      label: "Performance & Health",
      sublabel: "Telemetry & MTTR",
      icon: Activity,
    },
    {
      id: "upload",
      label: "Project Ingestion",
      sublabel: "ZIP / Git clone",
      icon: UploadCloud,
    },
    {
      id: "bug-detail",
      label: "Issue Dossier",
      sublabel: "Root cause & diff",
      icon: FileCode2,
      disabled: !hasActiveBug,
    },
    {
      id: "export",
      label: "Releases & PRs",
      sublabel: "Export & Git branch",
      icon: GitPullRequest,
    },
  ];

  return (
    <aside
      className="w-16 md:w-60 border-r border-slate-200 dark:border-sentry-border bg-white dark:bg-sentry-bg flex flex-col justify-between py-3.5 transition-all shrink-0 select-none"
      aria-label="Application Sidebar Navigation"
    >
      <div className="space-y-4">
        {/* Navigation Section Title */}
        <div className="px-3 hidden md:block">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Remediation Platform
          </span>
        </div>

        <nav className="space-y-1 px-2" role="navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentScreen === item.id;
            const isDisabled = item.disabled;

            return (
              <button
                key={item.id}
                onClick={() => !isDisabled && onNavigate(item.id as NavScreen)}
                disabled={isDisabled}
                aria-current={isActive ? "page" : undefined}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${
                  isActive
                    ? "bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 font-semibold border border-purple-200/80 dark:border-purple-800/60 shadow-2xs"
                    : isDisabled
                    ? "text-slate-300 dark:text-slate-700 cursor-not-allowed"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-sentry-cardHover hover:text-slate-900 dark:hover:text-slate-100"
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <Icon
                    className={`w-4 h-4 shrink-0 transition-colors ${
                      isActive
                        ? "text-purple-600 dark:text-purple-400"
                        : "text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300"
                    }`}
                  />
                  <div className="hidden md:flex flex-col text-left">
                    <span className="leading-tight">{item.label}</span>
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-normal">
                      {item.sublabel}
                    </span>
                  </div>
                </div>

                {item.badge !== undefined && (
                  <span
                    className={`hidden md:inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-bold font-mono ${item.badgeColor || "bg-slate-100 dark:bg-sentry-card text-slate-600 dark:text-slate-300"}`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sentry-Style Bottom Card: System Status & Guarantees */}
      <div className="px-3 hidden md:block">
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-sentry-card border border-slate-200 dark:border-sentry-border space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-500 dark:text-slate-400 font-medium">Engine Status</span>
            <span className="inline-flex items-center space-x-1 text-emerald-500 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Healthy</span>
            </span>
          </div>

          <div className="text-[10px] text-slate-400 dark:text-slate-500 border-t border-slate-200 dark:border-sentry-border/60 pt-2 space-y-1">
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
              <span>Isolated Execution Sandbox</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              <span>Zero-Regression Invariant</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
