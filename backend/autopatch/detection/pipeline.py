"""Detection pipeline orchestrator with cancellation support and evaluation metrics."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from autopatch.core.logging import get_logger
from autopatch.detection.aggregator import deduplicate_and_merge_findings
from autopatch.detection.ast_rules import ASTRuleDetector
from autopatch.detection.base import BaseDetector, CancellationToken, DetectionCancelledError
from autopatch.detection.input_validation import InputValidationDetector
from autopatch.detection.linter_adapters import LinterSuiteAdapter
from autopatch.detection.models import DetectionReport, Finding
from autopatch.detection.security import SecurityDetector
from autopatch.detection.test_failures import TestFailureDetector
from autopatch.intelligence.models import FileASTIndex

logger = get_logger(__name__)


class DetectionPipeline:
    """Orchestrates multi-detector execution, deduplication, and metrics reporting."""

    def __init__(self, detectors: Optional[List[BaseDetector]] = None):
        self.detectors = detectors or [
            ASTRuleDetector(),
            InputValidationDetector(),
            SecurityDetector(),
            LinterSuiteAdapter(),
            TestFailureDetector(),
        ]

    def run(
        self,
        project_id: str,
        project_root: Path,
        file_indices: List[FileASTIndex],
        cancel_token: Optional[CancellationToken] = None,
    ) -> DetectionReport:
        """Executes all registered detectors and returns a consolidated DetectionReport."""
        start_time = time.perf_counter()
        raw_findings: List[Finding] = []
        detectors_run: List[str] = []

        try:
            for detector in self.detectors:
                if cancel_token:
                    cancel_token.check_cancelled()

                logger.info(
                    f"Running detector {detector.name}",
                    extra={"data": {"project_id": project_id, "detector": detector.name}},
                )
                findings = detector.detect(project_root, file_indices, cancel_token)
                raw_findings.extend(findings)
                detectors_run.append(detector.name)

            if cancel_token:
                cancel_token.check_cancelled()

            # Deduplicate and merge overlapping findings
            merged_findings = deduplicate_and_merge_findings(raw_findings)
            elapsed = time.perf_counter() - start_time

            return DetectionReport(
                project_id=project_id,
                findings=merged_findings,
                total_findings=len(merged_findings),
                detectors_run=detectors_run,
                execution_time_seconds=round(elapsed, 4),
                cancelled=False,
                metadata={"raw_count": len(raw_findings), "merged_count": len(merged_findings)},
            )

        except DetectionCancelledError:
            elapsed = time.perf_counter() - start_time
            logger.info("Detection pipeline execution was cancelled.", extra={"data": {"project_id": project_id}})
            return DetectionReport(
                project_id=project_id,
                findings=[],
                total_findings=0,
                detectors_run=detectors_run,
                execution_time_seconds=round(elapsed, 4),
                cancelled=True,
                metadata={"status": "cancelled"},
            )

    @staticmethod
    def evaluate_precision_recall(
        known_bugs: List[Dict[str, Any]],
        detected_findings: List[Finding],
    ) -> Tuple[float, float]:
        """Calculates recall and precision against a seeded ground truth dataset.

        Args:
            known_bugs: List of dicts specifying {"file": str, "line": int}
            detected_findings: List of Finding objects produced by the pipeline

        Returns:
            Tuple of (recall, precision)
        """
        if not known_bugs:
            return 0.0, 1.0 if not detected_findings else 0.0

        matched_known_bugs: Set[int] = set()
        true_positives = 0

        for finding in detected_findings:
            matched = False
            for idx, bug in enumerate(known_bugs):
                if bug["file"] == finding.file:
                    bug_line = bug["line"]
                    # Match if finding encompasses bug line with standard +/-2 line tolerance
                    if (finding.line_start - 2) <= bug_line <= (finding.line_end + 2):
                        matched_known_bugs.add(idx)
                        matched = True
                        break
            if matched:
                true_positives += 1

        false_positives = len(detected_findings) - true_positives
        false_negatives = len(known_bugs) - len(matched_known_bugs)

        recall = len(matched_known_bugs) / len(known_bugs)
        precision = true_positives / (true_positives + false_positives) if detected_findings else 0.0

        return round(recall, 4), round(precision, 4)
