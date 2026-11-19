"""Token budget management and graceful degradation policies per bug and scan job."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple
from autopatch.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_JOB_BUDGET = 25_000   # Hard token ceiling per job
DEFAULT_BUG_BUDGET = 5_000     # Token ceiling per defect before degrading
FALLBACK_MODEL = "claude-3-haiku"
PRIMARY_MODEL = "claude-3-5-sonnet"


class TokenBudgetManager:
    """
    Manages hard token caps per bug and per job with graceful degradation.
    When a single bug crosses its limit, it transitions into degraded mode
    (falling back to deterministic template fixes and cheaper models).
    When an entire job crosses its cap, new bugs are skipped cleanly to report partial results.
    """

    def __init__(
        self,
        default_job_budget: int = DEFAULT_JOB_BUDGET,
        default_bug_budget: int = DEFAULT_BUG_BUDGET,
        primary_model: str = PRIMARY_MODEL,
        fallback_model: str = FALLBACK_MODEL,
    ) -> None:
        self.default_job_budget = default_job_budget
        self.default_bug_budget = default_bug_budget
        self.primary_model = primary_model
        self.fallback_model = fallback_model

        self._job_budgets: Dict[str, int] = {}
        self._bug_budgets: Dict[str, int] = {}
        self._job_tokens: Dict[str, int] = {}
        self._bug_tokens: Dict[str, int] = {}
        self._exceeded_jobs: Set[str] = set()
        self._degraded_bugs: Set[str] = set()

    def set_job_budget(self, job_id: str, budget: int) -> None:
        """Sets an explicit token limit for a scan job."""
        self._job_budgets[job_id] = max(0, budget)

    def set_bug_budget(self, bug_id: str, budget: int) -> None:
        """Sets an explicit token limit for a specific bug."""
        self._bug_budgets[bug_id] = max(0, budget)

    def get_job_budget(self, job_id: str) -> int:
        return self._job_budgets.get(job_id, self.default_job_budget)

    def get_bug_budget(self, bug_id: str) -> int:
        return self._bug_budgets.get(bug_id, self.default_bug_budget)

    def get_job_tokens(self, job_id: str) -> int:
        return self._job_tokens.get(job_id, 0)

    def get_bug_tokens(self, bug_id: str) -> int:
        return self._bug_tokens.get(bug_id, 0)

    def is_job_exceeded(self, job_id: str) -> bool:
        """Returns True if the cumulative job tokens have exceeded the job limit."""
        if job_id in self._exceeded_jobs:
            return True
        spent = self._job_tokens.get(job_id, 0)
        limit = self.get_job_budget(job_id)
        if spent >= limit:
            self._exceeded_jobs.add(job_id)
            return True
        return False

    def is_bug_degraded(self, bug_id: Optional[str]) -> bool:
        """Returns True if the bug has exceeded its budget and entered degraded mode."""
        if not bug_id:
            return False
        if bug_id in self._degraded_bugs:
            return True
        spent = self._bug_tokens.get(bug_id, 0)
        limit = self.get_bug_budget(bug_id)
        if spent >= limit:
            self._degraded_bugs.add(bug_id)
            return True
        return False

    def mark_bug_degraded(self, bug_id: str) -> None:
        """Explicitly forces a bug into graceful degradation mode."""
        self._degraded_bugs.add(bug_id)

    def consume(
        self,
        job_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        bug_id: Optional[str] = None,
    ) -> Tuple[bool, bool, bool]:
        """
        Records token spend and checks budget status.
        Returns:
            Tuple[job_ok, bug_ok, is_degraded]
            - job_ok: True if cumulative job spend is still within job budget.
            - bug_ok: True if cumulative bug spend is still within bug budget.
            - is_degraded: True if the bug is currently in degradation mode.
        """
        tokens = max(0, prompt_tokens) + max(0, completion_tokens)
        self._job_tokens[job_id] = self._job_tokens.get(job_id, 0) + tokens
        job_limit = self.get_job_budget(job_id)

        job_ok = self._job_tokens[job_id] <= job_limit
        if not job_ok:
            self._exceeded_jobs.add(job_id)
            logger.warning(
                f"Job {job_id} exceeded token budget: spent {self._job_tokens[job_id]}/{job_limit}"
            )

        bug_ok = True
        is_degraded = False

        if bug_id:
            self._bug_tokens[bug_id] = self._bug_tokens.get(bug_id, 0) + tokens
            bug_limit = self.get_bug_budget(bug_id)
            if self._bug_tokens[bug_id] > bug_limit:
                bug_ok = False
                self._degraded_bugs.add(bug_id)
                is_degraded = True
                logger.info(
                    f"Bug {bug_id} exceeded per-bug budget: spent {self._bug_tokens[bug_id]}/{bug_limit}. "
                    f"Degrading to template fixes and {self.fallback_model}."
                )
            elif bug_id in self._degraded_bugs:
                is_degraded = True
                bug_ok = False

        return job_ok, bug_ok, is_degraded

    def get_model_for_bug(
        self,
        bug_id: Optional[str] = None,
        preferred_model: Optional[str] = None,
    ) -> str:
        """
        Returns the appropriate LLM model:
        falls back to cheaper model (e.g. claude-3-haiku) if degraded.
        """
        if bug_id and self.is_bug_degraded(bug_id):
            return self.fallback_model
        return preferred_model or self.primary_model

    def should_use_template_only(self, bug_id: Optional[str] = None) -> bool:
        """
        Returns True if multi-turn LLM generation should be bypassed in favor of
        deterministic template repairs.
        """
        if bug_id and self.is_bug_degraded(bug_id):
            return True
        return False

    def get_budget_status(self, job_id: str, bug_id: Optional[str] = None) -> Dict[str, Any]:
        """Provides an inspection dictionary of current budget usage and flags."""
        job_spent = self.get_job_tokens(job_id)
        job_limit = self.get_job_budget(job_id)
        status: Dict[str, Any] = {
            "job_id": job_id,
            "job_tokens_spent": job_spent,
            "job_tokens_limit": job_limit,
            "job_budget_remaining": max(0, job_limit - job_spent),
            "job_exceeded": self.is_job_exceeded(job_id),
        }
        if bug_id:
            bug_spent = self.get_bug_tokens(bug_id)
            bug_limit = self.get_bug_budget(bug_id)
            status.update({
                "bug_id": bug_id,
                "bug_tokens_spent": bug_spent,
                "bug_tokens_limit": bug_limit,
                "bug_budget_remaining": max(0, bug_limit - bug_spent),
                "bug_degraded": self.is_bug_degraded(bug_id),
                "model_selected": self.get_model_for_bug(bug_id),
                "template_only": self.should_use_template_only(bug_id),
            })
        return status

    def reset(self, job_id: Optional[str] = None) -> None:
        """Resets budgets and tracking for a job or globally."""
        if job_id:
            self._job_budgets.pop(job_id, None)
            self._job_tokens.pop(job_id, None)
            self._exceeded_jobs.discard(job_id)
        else:
            self._job_budgets.clear()
            self._bug_budgets.clear()
            self._job_tokens.clear()
            self._bug_tokens.clear()
            self._exceeded_jobs.clear()
            self._degraded_bugs.clear()


# Shared global token budget manager instance
global_budget_manager = TokenBudgetManager()
