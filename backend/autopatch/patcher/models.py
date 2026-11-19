"""Data models for candidate patches, strict patch tags, and diff validation."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator

from autopatch.core.exceptions import TestModificationForbiddenError
from autopatch.core.models import TEST_FILE_PATTERNS


class CandidatePatch(BaseModel):
    """Candidate source code patch.

    Emitted in the strict format:
    <file>path</file><original>exact lines</original><patched>replacement lines</patched>
    plus rationale and risk notes.
    """

    id: UUID = Field(default_factory=uuid4)
    file: str = Field(min_length=1, description="Target file path")
    original_snippet: str = Field(description="Exact original code to be replaced")
    patched_snippet: str = Field(description="Replacement code")
    unified_diff: str = Field(default="", description="Unified diff formatted for git apply")
    rationale: str = Field(min_length=5, description="Plain-language explanation tied to root cause")
    risk_notes: str = Field(default="", description="Potential risks or side-effect considerations")
    source: str = Field(default="LLM", description="'TEMPLATE' or 'LLM'")
    template_name: Optional[str] = None
    ast_node_delta: int = Field(ge=0, default=0)
    lines_added: int = Field(ge=0, default=0)
    lines_deleted: int = Field(ge=0, default=0)
    flags_signature_change: bool = False
    applies_cleanly: bool = True
    validation_errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("file")
    @classmethod
    def validate_not_test_file(cls, v: str) -> str:
        """Enforces Rule 3: No patch modifies test files."""
        for pattern in TEST_FILE_PATTERNS:
            if pattern.search(v):
                raise TestModificationForbiddenError(
                    f"Candidate patch rejected: cannot target test file '{v}'. "
                    "Rule 3 strictly prohibits patches from modifying existing tests."
                )
        return v

    def to_xml_format(self) -> str:
        """Renders patch into strict tag format."""
        return (
            f"<file>{self.file}</file>\n"
            f"<original>\n{self.original_snippet}\n</original>\n"
            f"<patched>\n{self.patched_snippet}\n</patched>\n"
            f"Rationale: {self.rationale}\n"
            f"Risk Notes: {self.risk_notes or 'None'}"
        )


class PatchGenerationResult(BaseModel):
    """Aggregated result containing candidate patches and retry telemetry."""

    bug_id: str
    candidate_patches: List[CandidatePatch] = Field(default_factory=list)
    retry_count: int = Field(ge=0, le=3, default=0)
    best_attempt: Optional[CandidatePatch] = None
    all_applied_cleanly: bool = True
    summary: str = ""
