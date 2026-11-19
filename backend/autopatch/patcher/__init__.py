"""Patcher Agent and deterministic repair templates."""

from autopatch.patcher.models import (
    CandidatePatch,
    PatchGenerationResult,
)
from autopatch.patcher.templates import (
    DeterministicTemplatePatcher,
)
from autopatch.patcher.diff_utils import (
    generate_unified_diff,
    validate_minimal_diff_rules,
    verify_patch_applies_cleanly,
)
from autopatch.patcher.agent import (
    PatcherAgent,
    MAX_RETRIES,
)

__all__ = [
    "CandidatePatch",
    "PatchGenerationResult",
    "DeterministicTemplatePatcher",
    "generate_unified_diff",
    "validate_minimal_diff_rules",
    "verify_patch_applies_cleanly",
    "PatcherAgent",
    "MAX_RETRIES",
]
