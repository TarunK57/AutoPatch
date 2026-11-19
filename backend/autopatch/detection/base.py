"""Base detector interface and cancellation token."""

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from autopatch.core.exceptions import AutoPatchError
from autopatch.detection.models import Finding
from autopatch.intelligence.models import FileASTIndex


class DetectionCancelledError(AutoPatchError):
    """Raised when a detection run is cancelled cooperatively."""
    pass


class CancellationToken:
    """Thread-safe cooperative cancellation token for long-running detection tasks."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """Signals that the running task should stop execution."""
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        """Returns True if cancellation has been requested."""
        return self._cancelled.is_set()

    def check_cancelled(self) -> None:
        """Raises DetectionCancelledError if cancellation was requested."""
        if self._cancelled.is_set():
            raise DetectionCancelledError("Bug detection pipeline cancelled by user or timeout.")


class BaseDetector(ABC):
    """Abstract base class for all pluggable detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the detector."""
        pass

    @abstractmethod
    def detect(
        self,
        project_root: Path,
        file_indices: List[FileASTIndex],
        cancel_token: Optional[CancellationToken] = None,
    ) -> List[Finding]:
        """Executes detection across the target project and returns normalized Findings."""
        pass
