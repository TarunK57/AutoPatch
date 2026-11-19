"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BugItem, Project, ScanJob, ApprovalStatus } from "@/types";
import { ApiService, getDemoBugs } from "@/services/api";
import { Header } from "@/components/layout/Header";
import { Sidebar, NavScreen } from "@/components/layout/Sidebar";
import { UploadScreen } from "@/components/upload/UploadScreen";
import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { BugQueueScreen } from "@/components/queue/BugQueueScreen";
import { BugReportScreen } from "@/components/bug/BugReportScreen";
import { LiveTracePanel } from "@/components/trace/LiveTracePanel";
import { ReviewActionModal } from "@/components/actions/ReviewActionModal";
import { ExportModal } from "@/components/export/ExportModal";
import { KeyboardShortcutsModal } from "@/components/common/KeyboardShortcutsModal";

export default function Home() {
  // Theme state
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  // Project and bugs state
  const [currentProject, setCurrentProject] = useState<Project | null>({
    project_id: "demo-proj-1",
    name: "E-Commerce Core",
    owner_id: "user_developer",
    total_files: 24,
    languages: ["Python", "TypeScript"],
    created_at: new Date().toISOString(),
    test_command: "pytest tests/ -v",
  });
  const [bugs, setBugs] = useState<BugItem[]>([]);
  const [selectedBug, setSelectedBug] = useState<BugItem | null>(null);

  // Job and UI state
  const [activeJob, setActiveJob] = useState<ScanJob | null>({
    job_id: "job-demo-scan-1",
    project_id: "demo-proj-1",
    status: "COMPLETED",
    progress: 100.0,
    total_bugs: 5,
    completed_bugs: 5,
    token_metrics: {
      prompt_tokens: 14200,
      completion_tokens: 3800,
      total_tokens: 18000,
      estimated_cost_usd: 0.0996,
      llm_calls_count: 12,
    },
    created_at: new Date().toISOString(),
  });
  const [currentScreen, setCurrentScreen] = useState<NavScreen>("dashboard");
  const [isLoading, setIsLoading] = useState(false);

  // Drawer & Modals state
  const [isTraceOpen, setIsTraceOpen] = useState(false);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [reviewModalState, setReviewModalState] = useState<{
    isOpen: boolean;
    initialAction: ApprovalStatus;
  }>({
    isOpen: false,
    initialAction: "APPROVED",
  });

  // Load initial bugs
  useEffect(() => {
    const loadBugs = async () => {
      setIsLoading(true);
      try {
        const bugList = await ApiService.listBugs(currentProject?.project_id || "demo-proj-1");
        setBugs(bugList);
        if (bugList.length > 0) {
          setSelectedBug(bugList[0]);
        }
      } catch {
        const fallback = getDemoBugs();
        setBugs(fallback);
        setSelectedBug(fallback[0]);
      } finally {
        setIsLoading(false);
      }
    };
    loadBugs();
  }, [currentProject?.project_id]);

  // Dark/Light theme sync with HTML class
  const handleToggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    if (typeof document !== "undefined") {
      if (nextTheme === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    }
  };

  // Human Review Decision Submission
  const handleReviewDecision = async (decision: ApprovalStatus, comment: string) => {
    if (!selectedBug || !currentProject) return;
    try {
      const res = await ApiService.submitDecision(
        currentProject.project_id,
        selectedBug.bug_id,
        decision,
        comment
      );

      // Update in-memory state
      const updatedBugs = bugs.map((b) => {
        if (b.bug_id === selectedBug.bug_id) {
          return {
            ...b,
            decision: {
              status: decision,
              reviewer_id: res.reviewer_id || "user_developer",
              comment,
              signature_hash: res.signature_hash || "sha256_mock_hash",
              timestamp: new Date().toISOString(),
            },
            is_patch_applied: decision === "APPROVED",
          };
        }
        return b;
      });

      setBugs(updatedBugs);
      const updatedCurrent = updatedBugs.find((b) => b.bug_id === selectedBug.bug_id);
      if (updatedCurrent) {
        setSelectedBug(updatedCurrent);
      }
    } catch (e) {
      console.error("Decision recording error:", e);
    }
  };

  // Keyboard navigation & shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input or textarea
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      switch (e.key) {
        case "a":
        case "A":
          if (selectedBug && (currentScreen === "bug-detail" || currentScreen === "queue")) {
            e.preventDefault();
            setReviewModalState({ isOpen: true, initialAction: "APPROVED" });
          }
          break;
        case "r":
        case "R":
          if (selectedBug && (currentScreen === "bug-detail" || currentScreen === "queue")) {
            e.preventDefault();
            setReviewModalState({ isOpen: true, initialAction: "REJECTED" });
          }
          break;
        case "n":
        case "N":
          if (selectedBug && (currentScreen === "bug-detail" || currentScreen === "queue")) {
            e.preventDefault();
            setReviewModalState({ isOpen: true, initialAction: "NEEDS_REVIEW" });
          }
          break;
        case "t":
        case "T":
          e.preventDefault();
          setIsTraceOpen((prev) => !prev);
          break;
        case "d":
        case "D":
          e.preventDefault();
          handleToggleTheme();
          break;
        case "?":
          e.preventDefault();
          setIsShortcutsOpen((prev) => !prev);
          break;
        case "Escape":
          e.preventDefault();
          if (reviewModalState.isOpen) {
            setReviewModalState({ isOpen: false, initialAction: "APPROVED" });
          } else if (isShortcutsOpen) {
            setIsShortcutsOpen(false);
          } else if (isExportOpen) {
            setIsExportOpen(false);
          } else if (isTraceOpen) {
            setIsTraceOpen(false);
          } else if (currentScreen === "bug-detail") {
            setCurrentScreen("queue");
          }
          break;
        case "j":
        case "J":
          // Next bug
          if (bugs.length > 0) {
            e.preventDefault();
            const currIdx = bugs.findIndex((b) => b.bug_id === selectedBug?.bug_id);
            const nextIdx = (currIdx + 1) % bugs.length;
            setSelectedBug(bugs[nextIdx]);
          }
          break;
        case "k":
        case "K":
          // Previous bug
          if (bugs.length > 0) {
            e.preventDefault();
            const currIdx = bugs.findIndex((b) => b.bug_id === selectedBug?.bug_id);
            const prevIdx = (currIdx - 1 + bugs.length) % bugs.length;
            setSelectedBug(bugs[prevIdx]);
          }
          break;
      }
    },
    [
      selectedBug,
      currentScreen,
      bugs,
      reviewModalState.isOpen,
      isShortcutsOpen,
      isExportOpen,
      isTraceOpen,
    ]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Project Setup Handlers
  const handleProjectCreated = (proj: Project) => {
    setCurrentProject(proj);
    setCurrentScreen("dashboard");
  };

  const handleStartScan = async (projectId: string) => {
    setIsLoading(true);
    try {
      const job = await ApiService.startScan(projectId);
      setActiveJob(job);
      setIsTraceOpen(true);
      // Fetch fresh bugs
      const freshBugs = await ApiService.listBugs(projectId);
      setBugs(freshBugs);
      if (freshBugs.length > 0) {
        setSelectedBug(freshBugs[0]);
      }
      setCurrentScreen("dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelJob = (jobId: string) => {
    if (activeJob && activeJob.job_id === jobId) {
      setActiveJob({ ...activeJob, status: "CANCELLED" });
    }
  };

  const handleSelectBug = (bug: BugItem) => {
    setSelectedBug(bug);
    setCurrentScreen("bug-detail");
  };

  const handleOpenReview = (action: ApprovalStatus = "APPROVED") => {
    setReviewModalState({ isOpen: true, initialAction: action });
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 dark:bg-[#090d16] text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* Top Header */}
      <Header
        currentProject={currentProject}
        activeJob={activeJob}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        onToggleTrace={() => setIsTraceOpen(!isTraceOpen)}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
        onOpenExport={() => setIsExportOpen(true)}
      />

      {/* Main Workspace with Sidebar */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          currentScreen={currentScreen}
          onNavigate={(screen) => {
            if (screen === "export") {
              setIsExportOpen(true);
            } else {
              setCurrentScreen(screen);
            }
          }}
          bugsCount={bugs.length}
          hasActiveBug={!!selectedBug}
        />

        {/* Viewport Content Area */}
        <main
          className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 scrollbar-thin"
          id="main-content"
          role="main"
          tabIndex={-1}
        >
          {isLoading && (
            <div className="max-w-7xl mx-auto space-y-4 animate-pulse">
              <div className="h-28 bg-slate-200 dark:bg-slate-800/60 rounded-xl" />
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="h-24 bg-slate-200 dark:bg-slate-800/60 rounded-xl" />
                <div className="h-24 bg-slate-200 dark:bg-slate-800/60 rounded-xl" />
                <div className="h-24 bg-slate-200 dark:bg-slate-800/60 rounded-xl" />
                <div className="h-24 bg-slate-200 dark:bg-slate-800/60 rounded-xl" />
              </div>
              <div className="h-80 bg-slate-200 dark:bg-slate-800/60 rounded-xl" />
            </div>
          )}

          {!isLoading && currentScreen === "upload" && (
            <UploadScreen
              onProjectCreated={handleProjectCreated}
              onStartScan={handleStartScan}
              isLoading={isLoading}
            />
          )}

          {!isLoading && currentScreen === "dashboard" && (
            <DashboardScreen
              project={currentProject}
              bugs={bugs}
              onNavigateToQueue={() => setCurrentScreen("queue")}
              onSelectBug={handleSelectBug}
            />
          )}

          {!isLoading && currentScreen === "queue" && (
            <BugQueueScreen
              bugs={bugs}
              onSelectBug={handleSelectBug}
              selectedBugId={selectedBug?.bug_id}
            />
          )}

          {!isLoading && currentScreen === "bug-detail" && selectedBug && (
            <BugReportScreen
              bug={selectedBug}
              onBack={() => setCurrentScreen("queue")}
              onOpenReview={handleOpenReview}
              onRequestAlternative={() => {
                alert("Generating alternative patch with temperature=0.2...");
              }}
            />
          )}
        </main>
      </div>

      {/* Slide-out Live Agent Trace Panel */}
      <LiveTracePanel
        job={activeJob}
        isOpen={isTraceOpen}
        onClose={() => setIsTraceOpen(false)}
        onCancelJob={handleCancelJob}
      />

      {/* Human Review Decision Modal */}
      {selectedBug && (
        <ReviewActionModal
          bug={selectedBug}
          isOpen={reviewModalState.isOpen}
          initialAction={reviewModalState.initialAction}
          onClose={() => setReviewModalState({ isOpen: false, initialAction: "APPROVED" })}
          onSubmit={handleReviewDecision}
          onRequestAlternative={() => {
            alert("Requested alternative candidate patch.");
          }}
        />
      )}

      {/* Export & PR Creation Modal */}
      {currentProject && (
        <ExportModal
          project={currentProject}
          bugs={bugs}
          isOpen={isExportOpen}
          onClose={() => setIsExportOpen(false)}
        />
      )}

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />
    </div>
  );
}
