"""Bug detection pipeline, specialized detectors, and aggregation."""

from autopatch.detection.models import (
    Finding,
    FindingCategory,
    DetectionReport,
)
from autopatch.detection.base import (
    BaseDetector,
    CancellationToken,
    DetectionCancelledError,
)
from autopatch.detection.ast_rules import ASTRuleDetector
from autopatch.detection.input_validation import InputValidationDetector
from autopatch.detection.security import SecurityDetector
from autopatch.detection.linter_adapters import LinterSuiteAdapter
from autopatch.detection.test_failures import TestFailureDetector
from autopatch.detection.llm_reviewer import LLMSemanticReviewer
from autopatch.detection.aggregator import (
    deduplicate_and_merge_findings,
    findings_overlap,
    merge_finding_cluster,
)
from autopatch.detection.pipeline import DetectionPipeline

__all__ = [
    "Finding",
    "FindingCategory",
    "DetectionReport",
    "BaseDetector",
    "CancellationToken",
    "DetectionCancelledError",
    "ASTRuleDetector",
    "InputValidationDetector",
    "SecurityDetector",
    "LinterSuiteAdapter",
    "TestFailureDetector",
    "LLMSemanticReviewer",
    "deduplicate_and_merge_findings",
    "findings_overlap",
    "merge_finding_cluster",
    "DetectionPipeline",
]
