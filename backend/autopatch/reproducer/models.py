"""Data models for the Reproducer Agent (Bug Reproduction Tests)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TestRunStatus(str, Enum):
    """Execution status of a reproduction test run."""
    __test__ = False

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"  # Compile, syntax, or environment/import setup failure


class TestRunResult(BaseModel):
    """Detailed output from executing a test file in the sandbox."""
    __test__ = False

    status: TestRunStatus
    exit_code: int
    stdout: str
    stderr: str
    failure_trace: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_seconds: float = 0.0


class AgentStep(BaseModel):
    """Record of an individual action taken by the Reproducer Agent."""

    step_number: int = Field(ge=1, le=25)
    action: str = Field(description="cat, code_search, edit, run_tests, finish")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    output: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BRTClassification(BaseModel):
    """Classification of a Bug Reproduction Test (Candidate vs Plausible).

    - Candidate BRT: Fails on buggy code due to the actual defect (not setup/environment error).
    - Plausible BRT: Candidate that additionally passes on the reference fix or verified patch.
    """

    is_candidate: bool = False
    is_plausible: bool = False
    failure_trace: Optional[str] = None
    failure_reason: Optional[str] = None
    llm_judge_verdict: bool = False
    llm_judge_reasoning: str = ""


class ReproductionResult(BaseModel):
    """Final output produced by the Reproducer agent for a bug."""

    bug_id: str
    test_file_path: Optional[str] = None
    test_code: Optional[str] = None
    classification: BRTClassification
    steps: List[AgentStep] = Field(default_factory=list)
    runs_sampled: int = 1
    candidate_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    plausible_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    unique_failure_traces: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
