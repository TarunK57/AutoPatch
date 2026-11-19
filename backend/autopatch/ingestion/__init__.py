"""Project ingestion, extraction, and topology mapping."""

from autopatch.ingestion.extractor import (
    SafeExtractor,
    IngestionError,
    DEFAULT_IGNORE_DIRS,
    DEFAULT_IGNORE_FILES,
)
from autopatch.ingestion.project_map import (
    ProjectMapper,
    ProjectMap,
    TreeNode,
)

__all__ = [
    "SafeExtractor",
    "IngestionError",
    "DEFAULT_IGNORE_DIRS",
    "DEFAULT_IGNORE_FILES",
    "ProjectMapper",
    "ProjectMap",
    "TreeNode",
]
