"""Unit tests verifying that detection pipeline execution is cooperatively cancelable."""

from pathlib import Path
import pytest
from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding
from autopatch.detection.pipeline import DetectionPipeline
from autopatch.intelligence.models import FileASTIndex


class SlowDummyDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "SLOW_DUMMY"

    def detect(self, project_root: Path, file_indices, cancel_token=None):
        if cancel_token:
            cancel_token.cancel()  # Signal cancellation mid-flight
            cancel_token.check_cancelled()
        return []


def test_detection_pipeline_cancellation(tmp_path: Path):
    """Acceptance criterion: detection pipeline run is cancelable."""
    project_root = tmp_path / "cancel_project"
    project_root.mkdir()
    (project_root / "dummy.py").write_text("x = 1")

    # 1. Pre-cancelled token
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled

    pipeline = DetectionPipeline()
    report = pipeline.run("proj_cancelled", project_root, [], cancel_token=token)

    assert report.cancelled is True
    assert report.total_findings == 0

    # 2. Mid-flight cancellation
    active_token = CancellationToken()
    mid_pipeline = DetectionPipeline(detectors=[SlowDummyDetector()])
    mid_report = mid_pipeline.run("proj_mid_cancel", project_root, [], cancel_token=active_token)

    assert mid_report.cancelled is True
    assert mid_report.total_findings == 0
