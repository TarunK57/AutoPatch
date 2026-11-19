"use client";

import React from "react";
import { Keyboard, X } from "lucide-react";

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: "A", description: "Accept patch (Approve & Apply) on selected bug" },
    { key: "R", description: "Reject candidate patch on selected bug" },
    { key: "N", description: "Mark bug as Needs-Review for peer discussion" },
    { key: "T", description: "Toggle Live Agent Trace & Telemetry Drawer" },
    { key: "D", description: "Toggle Dark / Light Theme" },
    { key: "?", description: "Open / Close this Keyboard Shortcuts Cheat-Sheet" },
    { key: "Esc", description: "Close any open dialog or return to Bug Queue" },
    { key: "J / K", description: "Navigate to next / previous bug in queue" },
    { key: "Enter", description: "Confirm modal action or submit review decision" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in font-sans">
      <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden">
        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500">
              <Keyboard className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              Keyboard Shortcuts
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-2 text-xs">
          {shortcuts.map((sc, i) => (
            <div
              key={i}
              className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800"
            >
              <span className="text-slate-700 dark:text-slate-300">{sc.description}</span>
              <kbd className="px-2 py-1 rounded bg-slate-200 dark:bg-slate-700 font-mono text-[11px] font-bold text-slate-800 dark:text-slate-200 shadow-inner">
                {sc.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="p-3 bg-slate-50 dark:bg-slate-950/60 border-t border-slate-100 dark:border-slate-800 text-center text-[11px] text-slate-400">
          Press <kbd className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 font-mono font-bold">Esc</kbd> anytime to dismiss
        </div>
      </div>
    </div>
  );
};
