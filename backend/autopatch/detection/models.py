"""Normalized Finding schema and detection report models."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class FindingCategory(str, Enum):
    """Classification categories for detected code flaws."""

    LOGIC_ERROR = "LOGIC_ERROR"
    INPUT_VALIDATION = "INPUT_VALIDATION"
    SECURITY = "SECURITY"
    RESOURCE_LEAK = "RESOURCE_LEAK"
    TEST_FAILURE = "TEST_FAILURE"
    EXCEPTION_HANDLING = "EXCEPTION_HANDLING"
    STYLE_LINT = "STYLE_LINT"


class Finding(BaseModel):
    """Normalized finding emitted by all detectors in the AutoPatch pipeline.

    Invariants:
    - Every finding MUST have non-empty, verbatim code evidence.
    - line_end must be >= line_start.
    - raw_confidence must be calibrated between 0.0 and 1.0.
    """

    file: str = Field(min_length=1, description="Relative path of affected file")
    line_start: int = Field(ge=1, description="Starting line number (1-indexed)")
    line_end: int = Field(ge=1, description="Ending line number (inclusive)")
    symbol: Optional[str] = Field(default=None, description="Enclosing class, function, or method")
    category: FindingCategory
    cwe: Optional[str] = Field(default=None, description="Common Weakness Enumeration ID (e.g. CWE-89)")
    evidence: str = Field(min_length=1, description="Exact code snippet or stack trace demonstrating the flaw")
    detector: str = Field(min_length=1, description="Identifier of the detector or tool")
    raw_confidence: float = Field(ge=0.0, le=1.0, description="Calibrated confidence score between 0.0 and 1.0")
    description: str = Field(min_length=5, description="Clear description of the root cause and flaw")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context (e.g. valid range, agreeing detectors)")

    @field_validator("evidence")
    @classmethod
    def validate_evidence_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Evidence must be non-empty and quote actual code or execution trace.")
        return stripped

    @model_validator(mode="after")
    def validate_line_bounds(self) -> "Finding":
        if self.line_end < self.line_start:
            raise ValueError(f"line_end ({self.line_end}) cannot be less than line_start ({self.line_start})")
        return self


class DetectionReport(BaseModel):
    """Aggregated output of a bug detection pipeline execution."""

    project_id: str
    findings: List[Finding]
    total_findings: int
    detectors_run: List[str]
    execution_time_seconds: float = Field(ge=0.0)
    cancelled: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
