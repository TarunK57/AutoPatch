"""Data models for the Locator Agent and Root Cause Analysis."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    """Specification of a tool call selected by the LLM."""

    tool: str = Field(description="Name of the code-search tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    reasoning: str = Field(default="", description="Why this specific tool call is required")


class EvidenceRecord(BaseModel):
    """Record of a single tool execution step in the evidence trail."""

    stratum: int = Field(ge=1, description="Stratum iteration (1 to 10)")
    tool_name: str
    arguments: Dict[str, Any]
    result_summary: str
    raw_result: Any = None
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BuggyLocation(BaseModel):
    """Pinpointed method-level buggy location."""

    file: str = Field(description="Relative path of file")
    class_name: Optional[str] = Field(default=None, description="Class name if method is in a class")
    method_name: str = Field(description="Method or function name")
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    score: float = Field(ge=0.0, le=1.0, default=1.0, description="Suspiciousness score / rank")
    rationale: str = Field(default="", description="Explanation of why this method is faulty")

    @property
    def qualified_name(self) -> str:
        if self.class_name:
            return f"{self.file}:{self.class_name}.{self.method_name}"
        return f"{self.file}:{self.method_name}"


class RootCause(BaseModel):
    """Comprehensive root cause deduction and evidence trail.

    Enforces Rule 1 (Trust): Ships with root cause, causal chain, trigger state,
    and complete verifiable evidence trail.
    """

    summary: str = Field(min_length=10, description="Executive summary of the defect")
    trigger_input_or_state: str = Field(
        min_length=5, description="Input condition or environment state that triggers the fault"
    )
    causal_chain: List[str] = Field(
        min_length=1, description="Ordered step-by-step propagation across files and methods"
    )
    buggy_locations: List[BuggyLocation] = Field(
        default_factory=list, description="Ranked list of suspect method-level locations"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Calibrated localization confidence")
    evidence_trail: List[EvidenceRecord] = Field(
        default_factory=list, description="Chronological log of every tool call and result"
    )
    ochiai_hints: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top-5 SBFL hints if test execution spectra were available"
    )
    strata_used: int = Field(default=1, ge=1, le=10, description="Number of stratified retrieval rounds executed")
    total_tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed, bounded by hard cap")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
