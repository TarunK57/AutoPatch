"""Secret redaction and sanitization engine for AutoPatch.

Enforces Rule 4 (Safety): All untrusted code runs in a network-disabled,
resource-limited sandbox. Redact secrets before sending code to any LLM.
"""

import re
from typing import Dict, List, NamedTuple, Tuple
from autopatch.core.exceptions import SecretLeakageError


class RedactedMatch(NamedTuple):
    secret_type: str
    original: str
    placeholder: str


# Regular expressions for common secret types and high-entropy API tokens
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    (
        "DATABASE_URI",
        re.compile(
            r"(?i)\b(?:postgres|postgresql|mysql|mongodb|redis)://(?:(?!\${)[a-zA-Z0-9_.-]+):(?:(?!\${)[^@\s]+)@[a-zA-Z0-9_.-]+(?::\d+)?(?:/[a-zA-Z0-9_.-]+)?"
        ),
    ),
    ("ANTHROPIC_KEY", re.compile(r"\bsk-ant-[a-zA-Z0-9_-]{20,90}\b")),
    ("OPENAI_KEY", re.compile(r"\bsk-(?!ant-)(?:proj-|live-)?[a-zA-Z0-9_-]{20,80}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS_SECRET_KEY", re.compile(r"(?i)\baws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[a-zA-Z0-9_]{36,255}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[0-9a-zA-Z-]{10,72}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b")),
    ("JWT_TOKEN", re.compile(r"\beyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*\b")),
    (
        "PASSWORD_ASSIGNMENT",
        re.compile(
            r"""(?ix)
            \b(password|passwd|pwd|secret|api_key|apikey|auth_token|access_token|client_secret)
            \s*[:=]\s*
            ['"](?!(?:\[REDACTED_))([^'"\r\n]{4,})['"]
            """
        ),
    ),
]


class SecretRedactor:
    """Detects and redacts credentials, API keys, and sensitive tokens from code and prompts.

    Maintains an invertible mapping allowing safe local de-anonymization if required,
    while guaranteeing that zero raw secrets enter any LLM context.
    """

    def __init__(self) -> None:
        self._mask_to_secret: Dict[str, str] = {}
        self._secret_to_mask: Dict[str, str] = {}
        self._counter: int = 0

    def _get_or_create_placeholder(self, secret_type: str, original: str) -> str:
        if original in self._secret_to_mask:
            return self._secret_to_mask[original]

        self._counter += 1
        placeholder = f"[REDACTED_{secret_type}_{self._counter}]"
        self._mask_to_secret[placeholder] = original
        self._secret_to_mask[original] = placeholder
        return placeholder

    def redact(self, text: str) -> Tuple[str, List[RedactedMatch]]:
        """Redacts all detected secrets in the input text.

        Returns:
            Tuple of (sanitized_text, list_of_redactions)
        """
        if not text:
            return text, []

        redactions: List[RedactedMatch] = []
        sanitized = text

        for secret_type, pattern in SECRET_PATTERNS:
            if secret_type == "PASSWORD_ASSIGNMENT":
                def replace_assignment(match: re.Match) -> str:
                    key_name = match.group(1)
                    val = match.group(2)
                    if val.startswith("[REDACTED_") or val.lower() in {
                        "dummy", "test", "fake", "xxx", "password", "none", "", "true", "false"
                    }:
                        return match.group(0)
                    placeholder = self._get_or_create_placeholder("CREDENTIAL", val)
                    redactions.append(RedactedMatch("CREDENTIAL", val, placeholder))
                    delim = match.group(0)[len(key_name):].split(val)[0]
                    quote = "'" if match.group(0).endswith("'") else '"'
                    return f"{key_name}{delim}{placeholder}{quote}"

                sanitized = pattern.sub(replace_assignment, sanitized)
            elif secret_type == "AWS_SECRET_KEY":
                def replace_aws_secret(match: re.Match) -> str:
                    val = match.group(1)
                    if val.startswith("[REDACTED_"):
                        return match.group(0)
                    placeholder = self._get_or_create_placeholder("AWS_SECRET_KEY", val)
                    redactions.append(RedactedMatch("AWS_SECRET_KEY", val, placeholder))
                    return match.group(0).replace(val, placeholder)

                sanitized = pattern.sub(replace_aws_secret, sanitized)
            else:
                def replace_token(match: re.Match) -> str:
                    token = match.group(0)
                    if token.startswith("[REDACTED_"):
                        return token
                    placeholder = self._get_or_create_placeholder(secret_type, token)
                    redactions.append(RedactedMatch(secret_type, token, placeholder))
                    return placeholder

                sanitized = pattern.sub(replace_token, sanitized)

        return sanitized, redactions

    def restore(self, text: str) -> str:
        """Restores redacted placeholders back to their original values in a safe local environment."""
        result = text
        for placeholder, original in self._mask_to_secret.items():
            result = result.replace(placeholder, original)
        return result

    def assert_no_secrets(self, text: str) -> None:
        """Enforces Rule 4 by raising SecretLeakageError if any high-confidence secret is found."""
        for secret_type, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                matched_str = match.group(0)
                # Skip if already a placeholder
                if "[REDACTED_" in matched_str:
                    continue
                snippet = matched_str[:8] + "..."
                raise SecretLeakageError(
                    f"Unredacted secret detected before LLM ingestion: {secret_type} ({snippet}). "
                    "Rule 4 requires all code to be sanitized before LLM dispatch."
                )


# Global helper instance for direct convenience
_redactor = SecretRedactor()


def redact_secrets(text: str) -> Tuple[str, List[RedactedMatch]]:
    """Sanitizes text by redacting all sensitive credentials and API tokens."""
    return _redactor.redact(text)


def assert_clean_prompt(text: str) -> None:
    """Verifies that no secrets exist in the prompt destined for an LLM."""
    _redactor.assert_no_secrets(text)
