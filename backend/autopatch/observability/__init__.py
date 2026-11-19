"""Observability subsystem for AutoPatch: structured tracing, LLM caching, token budgets, cost dashboard, and replay."""

from autopatch.observability.models import (
    AgentStepTrace,
    ProjectCostSummary,
    ReplayResult,
    TraceOutcome,
)
from autopatch.observability.tracing import (
    StructuredTracer,
    compute_prompt_hash,
    global_tracer,
)
from autopatch.observability.cache import (
    CachedLLMResponse,
    LLMCache,
    compute_cache_key,
    global_llm_cache,
)
from autopatch.observability.budget import (
    TokenBudgetManager,
    global_budget_manager,
)
from autopatch.observability.dashboard import (
    CostDashboardService,
    global_dashboard_service,
)
from autopatch.observability.replay import (
    ReplayEngine,
    global_replay_engine,
)

__all__ = [
    "AgentStepTrace",
    "ProjectCostSummary",
    "ReplayResult",
    "TraceOutcome",
    "StructuredTracer",
    "compute_prompt_hash",
    "global_tracer",
    "CachedLLMResponse",
    "LLMCache",
    "compute_cache_key",
    "global_llm_cache",
    "TokenBudgetManager",
    "global_budget_manager",
    "CostDashboardService",
    "global_dashboard_service",
    "ReplayEngine",
    "global_replay_engine",
]
