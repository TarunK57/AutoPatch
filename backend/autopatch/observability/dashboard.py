"""Cost dashboard service aggregating token metrics, financial costs, and cache savings per project."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from autopatch.core.logging import get_logger
from autopatch.observability.cache import LLMCache, global_llm_cache
from autopatch.observability.models import ProjectCostSummary
from autopatch.observability.tracing import StructuredTracer, global_tracer

logger = get_logger(__name__)


class CostDashboardService:
    """
    Aggregates structured traces and cache metrics into high-level project cost summaries.
    Enables project-level financial visibility, agent breakdowns, and cache ROI reporting.
    """

    def __init__(
        self,
        tracer: Optional[StructuredTracer] = None,
        cache: Optional[LLMCache] = None,
    ) -> None:
        self.tracer = tracer or global_tracer
        self.cache = cache or global_llm_cache

    def get_project_cost_summary(
        self,
        project_id: str,
        job_ids: Optional[List[str]] = None,
        jobs_db: Optional[Dict[str, Any]] = None,
    ) -> ProjectCostSummary:
        """Computes financial spend, token consumption, and cache metrics for a project."""
        # 1. Resolve job IDs associated with this project
        target_jobs: List[str] = []
        if job_ids is not None:
            target_jobs = list(job_ids)
        elif jobs_db is not None:
            target_jobs = [
                jid for jid, info in jobs_db.items()
                if isinstance(info, dict) and info.get("project_id") == project_id
            ]

        # 2. Query traces for all target jobs (or all traces if none specified)
        all_traces = []
        if target_jobs:
            for jid in target_jobs:
                all_traces.extend(self.tracer.get_traces(job_id=jid))
        else:
            # Fallback to all traces in the tracer
            all_traces = self.tracer.get_traces()

        total_jobs_count = len(target_jobs) if target_jobs else (len(set(t.job_id for t in all_traces)) if all_traces else 0)

        # 3. Aggregate token counts, costs, and agent/model distributions
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        total_cost_usd = 0.0
        total_llm_calls = len(all_traces)
        total_cache_hits = 0

        agent_costs: Dict[str, float] = {}
        model_costs: Dict[str, float] = {}
        bug_aggregates: Dict[str, Dict[str, Any]] = {}

        for trace in all_traces:
            total_prompt_tokens += trace.prompt_tokens
            total_completion_tokens += trace.completion_tokens
            total_tokens += trace.total_tokens
            total_cost_usd += trace.estimated_cost_usd

            if trace.cached:
                total_cache_hits += 1

            # Breakdown by agent
            agent = trace.agent_name or "Unknown"
            agent_costs[agent] = round(agent_costs.get(agent, 0.0) + trace.estimated_cost_usd, 6)

            # Breakdown by model
            model = trace.model_used or "default"
            model_costs[model] = round(model_costs.get(model, 0.0) + trace.estimated_cost_usd, 6)

            # Breakdown by bug
            if trace.bug_id:
                if trace.bug_id not in bug_aggregates:
                    bug_aggregates[trace.bug_id] = {
                        "bug_id": trace.bug_id,
                        "job_id": trace.job_id,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "estimated_cost_usd": 0.0,
                        "calls_count": 0,
                    }
                bagg = bug_aggregates[trace.bug_id]
                bagg["prompt_tokens"] += trace.prompt_tokens
                bagg["completion_tokens"] += trace.completion_tokens
                bagg["total_tokens"] += trace.total_tokens
                bagg["estimated_cost_usd"] = round(bagg["estimated_cost_usd"] + trace.estimated_cost_usd, 6)
                bagg["calls_count"] += 1

        # Calculate cache metrics
        cache_stats = self.cache.get_stats()
        cache_hit_rate = (total_cache_hits / total_llm_calls * 100.0) if total_llm_calls > 0 else cache_stats.get("hit_rate_pct", 0.0)
        cost_saved_usd = cache_stats.get("cost_saved_usd", 0.0)

        # Sort top expensive bugs
        top_expensive = sorted(
            bug_aggregates.values(),
            key=lambda b: (b["estimated_cost_usd"], b["total_tokens"]),
            reverse=True,
        )[:10]

        return ProjectCostSummary(
            project_id=project_id,
            total_jobs=total_jobs_count,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost_usd, 6),
            total_llm_calls=total_llm_calls,
            total_cache_hits=total_cache_hits,
            cache_hit_rate=round(cache_hit_rate, 2),
            cost_saved_usd=round(cost_saved_usd, 6),
            agent_costs=agent_costs,
            model_costs=model_costs,
            top_expensive_bugs=top_expensive,
            generated_at=datetime.now(timezone.utc),
        )


# Shared global dashboard service instance
global_dashboard_service = CostDashboardService()
