from autopatch.security.redaction import (
    SecretRedactor,
    RedactedMatch,
    redact_secrets,
    assert_clean_prompt,
)
from autopatch.security.prompt_defense import (
    sanitize_untrusted_code,
    sanitize_untrusted_issue_text,
    build_hardened_system_prompt,
    ToolCallSecurityValidator,
)
from autopatch.security.dependency_scanner import DependencyScanner
from autopatch.security.retention import DataRetentionManager, RetentionPolicy, PurgeReport
from autopatch.security.privacy_mode import PrivacyGuard, PrivacyModeViolationError

__all__ = [
    "SecretRedactor",
    "RedactedMatch",
    "redact_secrets",
    "assert_clean_prompt",
    "sanitize_untrusted_code",
    "sanitize_untrusted_issue_text",
    "build_hardened_system_prompt",
    "ToolCallSecurityValidator",
    "DependencyScanner",
    "DataRetentionManager",
    "RetentionPolicy",
    "PurgeReport",
    "PrivacyGuard",
    "PrivacyModeViolationError",
]
