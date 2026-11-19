"use client";

import React, { useState } from "react";
import { ApprovalStatus, BugItem } from "@/types";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  MessageSquare,
  Lock,
  Sparkles,
  X,
  ShieldCheck,
  Send,
} from "lucide-react";

interface ReviewActionModalProps {
  bug: BugItem;
  isOpen: boolean;
  initialAction?: ApprovalStatus;
  onClose: () => void;
  onSubmit: (action: ApprovalStatus, comment: string) => Promise<void>;
  onRequestAlternative?: () => void;
}

export const ReviewActionModal: React.FC<ReviewActionModalProps> = ({
  bug,
  isOpen,
  initialAction = "APPROVED",
  onClose,
  onSubmit,
  onRequestAlternative,
}) => {
  const [action, setAction] = useState<ApprovalStatus>(initialAction);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSubmit(action, comment);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden font-sans">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                Human Review & Decision
              </h2>
              <p className="text-xs text-slate-500 font-mono">
                Target: {bug.bug_id} ({bug.file_path})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Invariant Note */}
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 flex items-start space-x-2.5">
            <Lock className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
            <span>
              <strong>Rule 1 Invariant:</strong> AutoPatch will never write to your files or create pull requests until you explicitly approve the patch here.
            </span>
          </div>

          {/* Action Choice Tabs */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Choose Decision Action:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {/* Accept */}
              <button
                type="button"
                onClick={() => setAction("APPROVED")}
                className={`p-3 rounded-xl border text-left transition-all ${
                  action === "APPROVED"
                    ? "bg-emerald-500/10 border-emerald-500 text-emerald-600 dark:text-emerald-400 ring-2 ring-emerald-500/20"
                    : "bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                <div className="flex items-center space-x-1.5 mb-1 font-semibold text-xs">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Accept (A)</span>
                </div>
                <div className="text-[10px] text-slate-500 leading-tight">
                  Approve and apply minimal patch.
                </div>
              </button>

              {/* Reject */}
              <button
                type="button"
                onClick={() => setAction("REJECTED")}
                className={`p-3 rounded-xl border text-left transition-all ${
                  action === "REJECTED"
                    ? "bg-red-500/10 border-red-500 text-red-600 dark:text-red-400 ring-2 ring-red-500/20"
                    : "bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                <div className="flex items-center space-x-1.5 mb-1 font-semibold text-xs">
                  <XCircle className="w-3.5 h-3.5 text-red-500" />
                  <span>Reject (R)</span>
                </div>
                <div className="text-[10px] text-slate-500 leading-tight">
                  Mark false positive or discard.
                </div>
              </button>

              {/* Needs Review */}
              <button
                type="button"
                onClick={() => setAction("NEEDS_REVIEW")}
                className={`p-3 rounded-xl border text-left transition-all ${
                  action === "NEEDS_REVIEW"
                    ? "bg-amber-500/10 border-amber-500 text-amber-600 dark:text-amber-400 ring-2 ring-amber-500/20"
                    : "bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                <div className="flex items-center space-x-1.5 mb-1 font-semibold text-xs">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  <span>Review (N)</span>
                </div>
                <div className="text-[10px] text-slate-500 leading-tight">
                  Request peer review / discussion.
                </div>
              </button>
            </div>
          </div>

          {/* Comment Area */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between">
              <span>Reviewer Comment / Rationale:</span>
              <span className="text-[11px] font-normal text-slate-400">Optional</span>
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g. Verified against production logs; patch accurately parameterizes input without side effects."
              rows={3}
              className="w-full p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
            />
          </div>

          {/* Alternative Patch Request Link */}
          {onRequestAlternative && (
            <div className="pt-1 flex items-center justify-between text-xs">
              <button
                type="button"
                onClick={() => {
                  onRequestAlternative();
                  onClose();
                }}
                className="text-indigo-600 dark:text-indigo-400 hover:underline flex items-center space-x-1"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Need another option? Request alternative LLM patch</span>
              </button>
            </div>
          )}

          {/* Footer Buttons */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
            <span className="text-[11px] text-slate-400">
              Press <strong>Enter</strong> to submit, <strong>Esc</strong> to cancel
            </span>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className={`flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold text-white shadow-sm transition-all ${
                  action === "APPROVED"
                    ? "bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500/40"
                    : action === "REJECTED"
                    ? "bg-red-600 hover:bg-red-700 focus:ring-red-500/40"
                    : "bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500/40"
                } ${isSubmitting ? "opacity-60 cursor-not-allowed" : ""}`}
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSubmitting ? "Recording..." : `Confirm ${action}`}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
