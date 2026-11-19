"""Token usage and execution cost tracking per scan job and agent invocation."""

from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field


# Standard Claude pricing per 1M tokens (e.g. Claude 3.5 Sonnet)
PRICING_PER_MILLION = {
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "default": {"input": 3.00, "output": 15.00},
}


class TokenMetrics(BaseModel):
    """Aggregate token consumption and financial cost metrics for a scan job."""

    prompt_tokens: int = Field(ge=0, default=0)
    completion_tokens: int = Field(ge=0, default=0)
    total_tokens: int = Field(ge=0, default=0)
    estimated_cost_usd: float = Field(ge=0.0, default=0.0)
    llm_calls_count: int = Field(ge=0, default=0)

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "claude-3-5-sonnet",
    ) -> None:
        """Records an individual LLM tool/call token usage and updates cumulative cost."""
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        self.llm_calls_count += 1

        pricing = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["default"])
        input_cost = (max(0, prompt_tokens) / 1_000_000.0) * pricing["input"]
        output_cost = (max(0, completion_tokens) / 1_000_000.0) * pricing["output"]
        self.estimated_cost_usd = round(self.estimated_cost_usd + input_cost + output_cost, 6)


class TokenUsageTracker:
    """Thread-safe manager maintaining token telemetry across all active jobs."""

    def __init__(self):
        self._metrics_by_job: Dict[str, TokenMetrics] = {}

    def get_or_create(self, job_id: str) -> TokenMetrics:
        if job_id not in self._metrics_by_job:
            self._metrics_by_job[job_id] = TokenMetrics()
        return self._metrics_by_job[job_id]

    def record(
        self,
        job_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "claude-3-5-sonnet",
    ) -> TokenMetrics:
        metrics = self.get_or_create(job_id)
        metrics.record_usage(prompt_tokens, completion_tokens, model)
        return metrics

    def get_metrics(self, job_id: str) -> TokenMetrics:
        return self.get_or_create(job_id)
