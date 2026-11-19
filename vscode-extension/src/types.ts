/**
 * Core type definitions for AutoPatch VS Code Extension.
 */

export type SeverityLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "STYLE";

export interface BugLocation {
  filePath: string;
  lineStart: number;
  lineEnd: number;
}

export interface CandidatePatch {
  patch_id: string;
  file: string;
  original_snippet: string;
  patched_snippet: string;
  unified_diff: string;
  rationale: string;
  confidence: number;
  strategy: string;
}

export interface BugItem {
  bug_id: string;
  file_path: string;
  line_start: number;
  line_end?: number;
  category: string;
  description: string;
  severity_level: SeverityLevel;
  confidence: number;
  priority_score: number;
  status: string;
  rank: number;
  patches?: CandidatePatch[];
  root_cause?: {
    summary: string;
    causal_chain?: string[];
  };
  verification?: {
    is_verified: boolean;
    regression_count: number;
  };
}

export interface ProjectResponse {
  project_id: string;
  name: string;
  owner_id: string;
  total_files: number;
  languages: string[];
  created_at: string;
}

export interface ScanJobResponse {
  job_id: string;
  project_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | "COMPLETED_PARTIAL";
  progress: number;
  total_bugs: number;
  completed_bugs: number;
  token_metrics?: {
    total_tokens: number;
    estimated_cost_usd: number;
    llm_calls_count: number;
  };
  created_at: string;
}
