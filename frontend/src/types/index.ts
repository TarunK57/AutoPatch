export type BugCategory = "security" | "data_loss" | "crash" | "wrong_output" | "style";

export type SeverityLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export type ApprovalStatus = "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "NEEDS_REVIEW";

export type VerificationState = "VERIFIED" | "PLAUSIBLE_BUT_UNVERIFIED" | "NEEDS_REVIEW" | "FAILED" | "NONE";

export interface Project {
  project_id: string;
  name: string;
  owner_id: string;
  total_files: number;
  languages: string[];
  created_at: string;
  test_command?: string;
}

export interface TokenMetrics {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  llm_calls_count: number;
}

export interface ScanJob {
  job_id: string;
  project_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress: number;
  total_bugs: number;
  completed_bugs: number;
  token_metrics: TokenMetrics;
  created_at: string;
}

export interface SeverityBreakdown {
  category: BugCategory;
  category_base_weight: number;
  reachability_status: string;
  reachability_factor: number;
  reachability_path: string[];
  callers_count: number;
  is_critical_path: boolean;
  critical_keywords_matched: string[];
  blast_radius_multiplier: number;
  numeric_severity: number;
  severity_level: SeverityLevel;
  explanation: string;
}

export interface ConfidenceBreakdown {
  detector_agreement_score: number;
  detector_agreement_weighted: number;
  brt_status: string;
  brt_score: number;
  brt_weighted: number;
  verification_state: string;
  verification_score: number;
  verification_weighted: number;
  epr: number;
  epr_score: number;
  epr_weighted: number;
  overfitting_flagged: boolean;
  overfitting_penalty: number;
  overall_confidence: number;
  explanation: string;
}

export interface ImpactBreakdown {
  callers_count: number;
  caller_boost: number;
  is_critical_path: boolean;
  critical_path_multiplier: number;
  reachability_factor: number;
  impact_score: number;
  explanation: string;
}

export interface PriorityScore {
  priority_score: number;
  severity: SeverityBreakdown;
  confidence: ConfidenceBreakdown;
  impact: ImpactBreakdown;
  rank: number;
  rank_explanation: string;
}

export interface CandidatePatch {
  id: string;
  file: string;
  original_snippet: string;
  patched_snippet: string;
  unified_diff: string;
  rationale: string;
  lines_added?: number;
  lines_deleted?: number;
  ensemble_pass_rate?: number;
}

export interface BugItem {
  bug_id: string;
  file_path: string;
  line_start: number;
  line_end: number;
  symbol?: string;
  category: BugCategory;
  description: string;
  evidence: string;
  severity_level: SeverityLevel;
  confidence: number;
  priority_score: number;
  status: string;
  rank: number;
  // Detailed fields
  finding?: Record<string, any>;
  root_cause?: {
    summary: string;
    trigger_input_or_state: string;
    causal_chain: string[];
    buggy_locations: string[];
    confidence: number;
    evidence_trail: string[];
  };
  reproduction?: {
    test_file_path: string;
    test_code: string;
    is_confirmed: boolean;
    exit_code: number;
    execution_log?: string;
  };
  patches?: CandidatePatch[];
  verification?: {
    status: VerificationState;
    ensemble_pass_rate: number;
    regressions_count: number;
    flakiness_stability_score: number;
    overfitting_detected: boolean;
    differential_divergent?: boolean;
    baseline_log?: string;
    patched_log?: string;
  };
  priority?: PriorityScore;
  decision?: {
    status: ApprovalStatus;
    reviewer_id: string;
    comment: string;
    signature_hash: string;
    timestamp: string;
  };
  is_patch_applied?: boolean;
}

export interface AuditEvent {
  id: string;
  event: string;
  job_id: string;
  bug_id?: string;
  seq: number;
  timestamp: string;
  actor: string;
  payload: Record<string, any>;
}
