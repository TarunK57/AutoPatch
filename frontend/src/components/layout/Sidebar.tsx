"use client";

import React from "react";
import {
  UploadCloud,
  LayoutDashboard,
  Bug,
  FileCode2,
  Terminal,
  Download,
  Settings2,
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
    { id: "upload", label: "Project Setup", icon: UploadCloud },
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "queue", label: "Bug Queue", icon: Bug, badge: bugsCount > 0 ? bugsCount : undefined },
    { id: "bug-detail", label: "Bug Dossier", icon: FileCode2, disabled: !hasActiveBug },
    { id: "export", label: "Export & PR", icon: Download },
  ];

  return (
    <aside
      className="w-16 md:w-56 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col justify-between py-3 transition-all shrink-0 select-none"
      aria-label="Application Sidebar Navigation"
    >
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
              className={`w-full flex items-center justify-center md:justify-between px-3 py-2 rounded-md text-xs font-medium transition-all ${
                isActive
                  ? "bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-semibold shadow-xs"
                  : isDisabled
                  ? "text-slate-300 dark:text-slate-700 cursor-not-allowed"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <Icon className={`w-4 h-4 ${isActive ? "text-indigo-600 dark:text-indigo-400" : ""}`} />
                <span className="hidden md:inline">{item.label}</span>
              </div>

              {item.badge !== undefined && (
                <span className="hidden md:inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="px-3 text-[11px] text-slate-400 dark:text-slate-600 hidden md:block">
        <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-1">
          <p className="font-semibold text-slate-500 dark:text-slate-400">AutoPatch v1.0.0</p>
          <p>Network-Isolated Sandbox</p>
          <p className="text-[10px]">Rule 1: Human Approval</p>
        </div>
      </div>
    </aside>
  );
};
