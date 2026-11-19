from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class TraceOutcome(str, Enum):
    """Categorical outcomes for an agent execution step."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ERROR = "ERROR"
    DEGRADED = "DEGRADED"
    CACHE_HIT = "CACHE_HIT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"


class AgentStepTrace(BaseModel):
    """Structured audit and telemetry record for a single discrete agent step."""
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    bug_id: Optional[str] = None
    agent_name: str  # "Locator", "Reproducer", "Patcher", "Verifier", "Orchestrator"
    stage: str       # "RETRIEVAL", "BRT_GENERATION", "PATCH_SYNTHESIS", etc.
    prompt_hash: str
    prompt_length: int = 0
    tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    outcome: TraceOutcome = TraceOutcome.SUCCESS
    cached: bool = False
    model_used: str = "claude-3-5-sonnet"
    estimated_cost_usd: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectCostSummary(BaseModel):
    """Aggregate financial and token telemetry for a project's cost dashboard."""
    project_id: str
    total_jobs: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_llm_calls: int = 0
    total_cache_hits: int = 0
    cache_hit_rate: float = 0.0
    cost_saved_usd: float = 0.0
    agent_costs: Dict[str, float] = Field(default_factory=dict)
    model_costs: Dict[str, float] = Field(default_factory=dict)
    top_expensive_bugs: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReplayResult(BaseModel):
    """Outcome of replaying a stored trace deterministically using cached responses."""
    target_id: str
    target_type: str  # "job" or "bug"
    total_steps_replayed: int = 0
    cache_hits: int = 0
    reproduced_decisions: int = 0
    is_exact_match: bool = True
    discrepancies: List[str] = Field(default_factory=list)
    replayed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
