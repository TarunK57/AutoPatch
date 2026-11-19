"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  ScanJob,
  TokenMetrics,
} from "@/types";
import {
  Activity,
  Terminal,
  Cpu,
  Coins,
  Square,
  Play,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowDownCircle,
  Filter,
  Maximize2,
  X,
} from "lucide-react";

interface AgentTraceEvent {
  id: string;
  timestamp: string;
  agent: "Locator" | "Reproducer" | "Patcher" | "Verifier" | "Orchestrator";
  step: string;
  message: string;
  type: "info" | "success" | "warn" | "error";
  tokens?: number;
}

interface LiveTracePanelProps {
  job: ScanJob | null;
  isOpen: boolean;
  onClose: () => void;
  onCancelJob?: (jobId: string) => void;
}

export const LiveTracePanel: React.FC<LiveTracePanelProps> = ({
  job,
  isOpen,
  onClose,
  onCancelJob,
}) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterAgent, setFilterAgent] = useState<string>("ALL");
  const [events, setEvents] = useState<AgentTraceEvent[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Simulated or SSE event generator when job is active
  useEffect(() => {
    if (!job) return;

    // Initial seed events
    const initialEvents: AgentTraceEvent[] = [
      {
        id: "ev-1",
        timestamp: "10:45:00",
        agent: "Orchestrator",
        step: "INGESTION",
        message: "Project files extracted cleanly (SafeExtractor: zip-slip verified, 24 files indexed).",
        type: "info",
      },
      {
        id: "ev-2",
        timestamp: "10:45:01",
        agent: "Orchestrator",
        step: "DETECTION",
        message: "Detector pipeline initialized 9 AST detectors, 4 linters and LLM reviewer. 5 findings emitted.",
        type: "info",
      },
      {
        id: "ev-3",
        timestamp: "10:45:02",
        agent: "Locator",
        step: "RETRIEVAL_STRATA_1",
        message: "AutoCodeRover search_method('get_user_by_token') -> 18 lines retrieved.",
        type: "info",
        tokens: 420,
      },
      {
        id: "ev-4",
        timestamp: "10:45:04",
        agent: "Locator",
        step: "OCHIAI_HINT",
        message: "Ochiai suspiciousness computed for 12 methods. Top hint: src/auth/service.py:get_user_by_token (0.948).",
        type: "success",
      },
      {
        id: "ev-5",
        timestamp: "10:45:06",
        agent: "Reproducer",
        step: "BRT_GENERATION",
        message: "Generating Fail-to-Pass reproduction test in sandbox (tests/test_brt_auth_sqli.py).",
        type: "info",
        tokens: 680,
      },
      {
        id: "ev-6",
        timestamp: "10:45:08",
        agent: "Reproducer",
        step: "BRT_EXECUTION",
        message: "Executed BRT on buggy snapshot: Result is FAIL (Exit Code 1). Confirmed candidate BRT.",
        type: "success",
      },
      {
        id: "ev-7",
        timestamp: "10:45:09",
        agent: "Patcher",
        step: "TEMPLATE_MATCH",
        message: "Matched deterministic template: Parameterized Query Fix for CWE-89 SQL Injection.",
        type: "info",
      },
      {
        id: "ev-8",
        timestamp: "10:45:10",
        agent: "Patcher",
        step: "MINIMAL_DIFF",
        message: "Minimal-diff check: +2 lines, -2 lines, 0 test modifications. Strict syntax check passed.",
        type: "success",
      },
      {
        id: "ev-9",
        timestamp: "10:45:12",
        agent: "Verifier",
        step: "SANDBOX_VERIFY",
        message: "Ephemeral Docker container run: BRT passes (Exit Code 0), existing suite passes with 0 regressions.",
        type: "success",
      },
      {
        id: "ev-10",
        timestamp: "10:45:13",
        agent: "Verifier",
        step: "ENSEMBLE_PASS_RATE",
        message: "Candidate ranked #1: EPR 100.0%, Diff Size 4 lines, Stability Score 1.0 (3x runs).",
        type: "success",
      },
    ];

    setEvents(initialEvents);

    // If job is still RUNNING, listen to SSE stream or periodic simulation
    if (job.status === "RUNNING") {
      const interval = setInterval(() => {
        const agents: Array<"Locator" | "Reproducer" | "Patcher" | "Verifier"> = [
          "Locator",
          "Reproducer",
          "Patcher",
          "Verifier",
        ];
        const randomAgent = agents[Math.floor(Math.random() * agents.length)];
        const newEvent: AgentTraceEvent = {
          id: `ev-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          agent: randomAgent,
          step: "STREAMED_STEP",
          message: `Active processing step on ${randomAgent} Agent: checking constraints and verifying sub-goals...`,
          type: "info",
          tokens: Math.floor(Math.random() * 200) + 50,
        };
        setEvents((prev) => [...prev, newEvent]);
      }, 4000);

      return () => clearInterval(interval);
    }
  }, [job]);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  if (!isOpen) return null;

  const filteredEvents = events.filter((ev) => {
    if (filterAgent === "ALL") return true;
    return ev.agent.toUpperCase() === filterAgent;
  });

  const tokens = job?.token_metrics || {
    prompt_tokens: 14200,
    completion_tokens: 3800,
    total_tokens: 18000,
    estimated_cost_usd: 0.0996,
    llm_calls_count: 12,
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl z-50 flex flex-col font-sans transition-all">
      {/* Top Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Activity className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-semibold text-white">Live Agent Trace Stream</h2>
              {job?.status === "RUNNING" ? (
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping mr-1" />
                  RUNNING
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  COMPLETED
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">
              Job ID: {job?.job_id || "demo-job-101"}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {job?.status === "RUNNING" && onCancelJob && (
            <button
              onClick={() => onCancelJob(job.job_id)}
              className="flex items-center space-x-1 px-2.5 py-1 rounded bg-red-950/40 hover:bg-red-900/60 text-red-300 text-xs font-medium border border-red-800/60 transition-colors"
            >
              <Square className="w-3 h-3 fill-current" />
              <span>Cancel Job</span>
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close Panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Token & Cost Telemetry Bar */}
      <div className="grid grid-cols-4 gap-2 p-3 bg-slate-950/60 border-b border-slate-800/80 text-xs">
        <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">Prompt Tokens</span>
          <span className="font-mono font-medium text-slate-200 mt-0.5 block">
            {tokens.prompt_tokens.toLocaleString()}
          </span>
        </div>
        <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">Completion Tokens</span>
          <span className="font-mono font-medium text-slate-200 mt-0.5 block">
            {tokens.completion_tokens.toLocaleString()}
          </span>
        </div>
        <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">LLM Calls</span>
          <span className="font-mono font-medium text-indigo-400 mt-0.5 block">
            {tokens.llm_calls_count} calls
          </span>
        </div>
        <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">Estimated Cost</span>
          <span className="font-mono font-medium text-emerald-400 mt-0.5 block">
            ${tokens.estimated_cost_usd.toFixed(4)}
          </span>
        </div>
      </div>

      {/* Stream Filter & Control Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center space-x-1.5 overflow-x-auto">
          <span className="text-slate-500 text-[11px] mr-1">Filter:</span>
          {["ALL", "LOCATOR", "REPRODUCER", "PATCHER", "VERIFIER"].map((agent) => (
            <button
              key={agent}
              onClick={() => setFilterAgent(agent)}
              className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                filterAgent === agent
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
              }`}
            >
              {agent}
            </button>
          ))}
        </div>

        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] transition-colors ${
            autoScroll
              ? "bg-slate-800 text-emerald-400 border border-emerald-500/20"
              : "bg-slate-800 text-slate-400 hover:text-slate-200"
          }`}
          title="Toggle autoscroll to latest events"
        >
          <ArrowDownCircle className="w-3 h-3" />
          <span>Auto-scroll</span>
        </button>
      </div>

      {/* Log Feed */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-2.5 font-mono text-xs bg-slate-950 scrollbar-thin"
      >
        {filteredEvents.map((ev) => (
          <div
            key={ev.id}
            className={`p-2.5 rounded border transition-colors ${
              ev.type === "success"
                ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-200"
                : ev.type === "warn"
                ? "bg-amber-950/20 border-amber-900/40 text-amber-200"
                : ev.type === "error"
                ? "bg-red-950/20 border-red-900/40 text-red-200"
                : "bg-slate-900/60 border-slate-800/80 text-slate-300"
            }`}
          >
            <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
              <div className="flex items-center space-x-2">
                <span className="text-slate-500">{ev.timestamp}</span>
                <span className={`px-1.5 py-0.2 rounded font-semibold text-[10px] ${
                  ev.agent === "Locator"
                    ? "bg-blue-500/20 text-blue-300"
                    : ev.agent === "Reproducer"
                    ? "bg-purple-500/20 text-purple-300"
                    : ev.agent === "Patcher"
                    ? "bg-amber-500/20 text-amber-300"
                    : ev.agent === "Verifier"
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-slate-700 text-slate-300"
                }`}>
                  {ev.agent}
                </span>
                <span className="text-slate-400">[{ev.step}]</span>
              </div>
              {ev.tokens && (
                <span className="text-slate-500 text-[10px]">
                  {ev.tokens} tok
                </span>
              )}
            </div>
            <div className="leading-relaxed whitespace-pre-wrap">{ev.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
};
