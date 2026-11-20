"""Pydantic schemas for the AutoPatch REST API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopatch.orchestrator.tokens import TokenMetrics


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    github_url: Optional[str] = Field(default=None, description="Optional GitHub URL for shallow clone")


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    owner_id: str
    total_files: int = 0
    languages: List[str] = Field(default_factory=lambda: ["python"])
    github_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StartScanRequest(BaseModel):
    entry_points: Optional[List[str]] = Field(default=None, description="Explicit application entry points")
    concurrency_limit: int = Field(ge=1, le=10, default=3)
    privacy_mode: bool = Field(default=False, description="Disables external LLM calls and runs local AST rules & templates only")



class ScanJobResponse(BaseModel):
    job_id: str
    project_id: str
    status: str
    progress: float = Field(ge=0.0, le=100.0, default=0.0)
    total_bugs: int = 0
    completed_bugs: int = 0
    token_metrics: TokenMetrics = Field(default_factory=TokenMetrics)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BugSummaryItem(BaseModel):
    bug_id: str
    file_path: str
    line_start: int
    category: str
    description: str
    severity_level: str
    severity: Optional[str] = None
    confidence: float
    priority_score: float
    status: str
    verification_status: Optional[str] = None
    rank: int = 1
    rank_explanation: Optional[str] = None
    cwe: Optional[str] = None
    symbol: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.severity is None:
            self.severity = self.severity_level
        if self.verification_status is None:
            self.verification_status = self.status


class BugListResponse(BaseModel):
    project_id: str
    total_bugs: int
    bugs: List[BugSummaryItem]
    items: Optional[List[BugSummaryItem]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.items is None:
            self.items = self.bugs


class BugDetailResponse(BaseModel):
    bug_id: str
    status: str
    finding: Optional[Dict[str, Any]] = None
    root_cause: Optional[Dict[str, Any]] = None
    reproduction: Optional[Dict[str, Any]] = None
    patches: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    priority: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    is_patch_applied: bool = False
    completed_stages: List[str] = Field(default_factory=list)


class PatchGenerationRequest(BaseModel):
    rationale_hint: Optional[str] = None


class ValidationRequest(BaseModel):
    patch_id: Optional[str] = None


class DecisionRequest(BaseModel):
    decision: Optional[str] = Field(default=None, pattern="^(APPROVED|REJECTED|NEEDS_REVIEW)$")
    status: Optional[str] = Field(default=None, pattern="^(APPROVED|REJECTED|NEEDS_REVIEW)$")
    comment: str = ""
    patch_id: Optional[str] = Field(default=None, description="Exact patch ID approved by reviewer")

    def model_post_init(self, __context: Any) -> None:
        if self.decision is None and self.status is not None:
            self.decision = self.status
        elif self.status is None and self.decision is not None:
            self.status = self.decision
        if self.decision is None:
            self.decision = "REJECTED"


class DecisionResponse(BaseModel):
    bug_id: str
    reviewer_id: str
    status: str
    comment: str
    signature_hash: str
    applied: bool = False
    patch_id: Optional[str] = None
    patch_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevertResponse(BaseModel):
    bug_id: str
    reverted: bool
    message: str


class HistoryResponse(BaseModel):
    project_id: str
    total_events: int
    events: List[Dict[str, Any]] = Field(default_factory=list)


class CreateRemediationBranchRequest(BaseModel):
    branch_name: str = Field(min_length=1, max_length=150, default="autopatch/remediation-patches")
    base_branch: str = Field(min_length=1, max_length=150, default="main")
    include_brt_tests: bool = True


class CreateRemediationBranchResponse(BaseModel):
    branch_name: str
    base_branch: str
    total_commits: int
    bugs_included: List[str]
    bugs_skipped: List[str]
    commits: List[Dict[str, Any]] = Field(default_factory=list)


class OpenPullRequestRequest(BaseModel):
    repo_slug: str = Field(description="e.g. owner/repo")
    head_branch: str
    base_branch: str = "main"
    title: Optional[str] = None
    github_token: Optional[str] = None


class OpenPullRequestResponse(BaseModel):
    pr_number: int
    html_url: str
    head_branch: str
    base_branch: str
    title: str
    body_markdown: str


class RevertCommitRequest(BaseModel):
    bug_id_or_commit_sha: str


class RevertCommitResponse(BaseModel):
    bug_id: str
    target_commit_sha: str
    revert_commit_sha: str
    is_clean: bool
    restored_files: List[str]
    message: str


class PurgeResponse(BaseModel):
    target_id: str
    target_type: str
    success: bool
    deleted_paths: List[str] = Field(default_factory=list)
    purged_events_count: int
    purged_jobs_count: int
    message: str


class GitHubUserResponse(BaseModel):
    login: str = "user"
    name: Optional[str] = "GitHub User"
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    public_repos: int = 0
    total_private_repos: int = 0


class GitHubRepoItem(BaseModel):
    id: Optional[int] = 0
    name: str = ""
    full_name: str = ""
    html_url: Optional[str] = ""
    clone_url: Optional[str] = ""
    default_branch: Optional[str] = "main"
    is_private: Optional[bool] = False
    description: Optional[str] = ""
    language: Optional[str] = "Other"
    stars: Optional[int] = 0
    forks: Optional[int] = 0
    updated_at: Optional[str] = None


class GitHubRepoListResponse(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    total_count: int
    repositories: List[GitHubRepoItem] = Field(default_factory=list)


class PushBranchRequest(BaseModel):
    branch_name: str
    remote_name: str = "origin"
    remote_url: Optional[str] = None
    github_token: Optional[str] = None


class PushBranchResponse(BaseModel):
    branch_name: str
    remote_name: str
    success: bool
    output: str


class GitHubOAuthConfigResponse(BaseModel):
    is_configured: bool
    client_id: Optional[str] = None
    scope: str = "repo,read:user"
    auth_url: Optional[str] = None


class GitHubPortalConnectRequest(BaseModel):
    username: Optional[str] = "NiharNeo"
    token: Optional[str] = None


class GitHubPortalConnectResponse(BaseModel):
    connected: bool
    user: GitHubUserResponse
    total_repositories: int
    repositories: List[GitHubRepoItem] = Field(default_factory=list)


class DashboardKpis(BaseModel):
    verification_rate: float = 0.0
    verification_rate_label: str = ""
    mttr_seconds: float = 0.0
    mttr_display: str = "0.0s"
    mttr_subtitle: str = ""
    vulnerabilities_resolved: int = 0
    vulnerabilities_total: int = 0
    vulnerabilities_pending: int = 0
    patches_applied: int = 0
    total_audit_events: int = 0
    total_projects: int = 0
    total_jobs: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    cache_hit_rate: float = 0.0


class CweCategoryItem(BaseModel):
    key: str
    label: str
    count: int
    percentage: float
    color: str


class VelocityPoint(BaseModel):
    label: str
    count: int


class VelocityCurveData(BaseModel):
    unit: str
    points: List[VelocityPoint] = Field(default_factory=list)


class DashboardActivityItem(BaseModel):
    event_id: str
    job_id: str
    bug_id: Optional[str] = None
    event_type: str
    actor: str
    timestamp: str
    time_ago: str
    title: str
    description: str
    badge_type: str = "info"


class ProjectSelectItem(BaseModel):
    project_id: str
    name: str


class DashboardTelemetryResponse(BaseModel):
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    generated_at: str
    kpis: DashboardKpis
    cwe_distribution: List[CweCategoryItem] = Field(default_factory=list)
    velocity_curve: VelocityCurveData
    recent_activities: List[DashboardActivityItem] = Field(default_factory=list)
    projects_list: List[ProjectSelectItem] = Field(default_factory=list)


# ============================================================================
# Advanced Intelligence Models
# ============================================================================

class PredictiveFindingItem(BaseModel):
    file: str
    line_start: int
    line_end: int
    symbol: Optional[str] = None
    hazard_type: str
    cwe: Optional[str] = None
    probability: float
    confidence: float
    description: str
    evidence: str
    recommendation: str


class PredictiveAnalysisResponse(BaseModel):
    project_id: str
    total_hazards_predicted: int
    high_probability_hazards_count: int
    average_failure_probability: float
    findings: List[PredictiveFindingItem] = Field(default_factory=list)


class CommitteeReviewRequest(BaseModel):
    bug_id: str
    file_path: str
    patch_diff: Optional[str] = None
    defect_description: Optional[str] = None
    root_cause_summary: Optional[str] = None


class DigitalTwinNode(BaseModel):
    id: str
    name: str
    full_id: Optional[str] = None
    type: str  # module | function | api_endpoint | test
    file_path: str
    line: int = 1
    loc: int = 0
    complexity: int = 1
    risk_score: int = 10
    category: str = "core"
    is_direct_target: bool = False
    is_affected: bool = False


class DigitalTwinEdge(BaseModel):
    source: str
    target: str
    relationship: str = "calls"
    is_blast_path: bool = False


class DigitalTwinMetrics(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    modules_count: int = 0
    functions_count: int = 0
    api_endpoints_count: int = 0
    tests_count: int = 0
    avg_risk_score: float = 0.0


class PatchBlastRadius(BaseModel):
    direct_targets: List[str] = Field(default_factory=list)
    affected_node_ids: List[str] = Field(default_factory=list)
    total_affected: int = 0
    blast_radius_pct: float = 0.0
    overall_risk_level: str = "LOW"
    critical_apis_at_risk: List[str] = Field(default_factory=list)
    tests_exercised: List[str] = Field(default_factory=list)
    functions_affected: List[str] = Field(default_factory=list)
    summary: str = ""


class DigitalTwinResponse(BaseModel):
    nodes: List[DigitalTwinNode] = Field(default_factory=list)
    edges: List[DigitalTwinEdge] = Field(default_factory=list)
    metrics: DigitalTwinMetrics = Field(default_factory=DigitalTwinMetrics)
    blast_radius: Optional[PatchBlastRadius] = None






