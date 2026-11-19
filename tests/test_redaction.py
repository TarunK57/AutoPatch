"""Unit tests for secret redaction engine and Rule 4 safety enforcement."""

import pytest
from autopatch.core.exceptions import SecretLeakageError
from autopatch.security.redaction import (
    SecretRedactor,
    assert_clean_prompt,
    redact_secrets,
)


def test_redact_api_keys():
    """Verify redaction of OpenAI, Anthropic, AWS, and GitHub tokens."""
    raw_code = """
    # Configuration setup
    openai_key = "sk-proj-abc123456789012345678901234567890"
    anthropic_key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
    aws_key = "AKIA1234567890ABCDEF"
    github_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
    """
    sanitized, matches = redact_secrets(raw_code)

    assert "sk-proj-" not in sanitized
    assert "sk-ant-" not in sanitized
    assert "AKIA1234567890ABCDEF" not in sanitized
    assert "ghp_" not in sanitized
    assert len(matches) >= 4

    # Assert no secrets remain in sanitized text
    assert_clean_prompt(sanitized)


def test_redact_passwords_and_assignments():
    """Verify redaction of passwords and database connection strings."""
    raw_code = """
    DB_URI = "postgres://admin:superSecretPassword99@db.internal:5432/production"
    password = "MySuperSecretPassword123!"
    secret = "TopSecretJWTTokenValue"
    """
    sanitized, matches = redact_secrets(raw_code)

    assert "superSecretPassword99" not in sanitized
    assert "MySuperSecretPassword123!" not in sanitized
    assert "TopSecretJWTTokenValue" not in sanitized
    assert "[REDACTED_" in sanitized

    # Clean verification passes
    assert_clean_prompt(sanitized)


def test_invertible_restoration():
    """Verify that redacted tokens can be restored back to original values."""
    redactor = SecretRedactor()
    raw = 'api_key = "sk-ant-test123456789012345678901234567890"'
    sanitized, matches = redactor.redact(raw)
    assert "sk-ant-" not in sanitized

    restored = redactor.restore(sanitized)
    assert restored == raw


def test_rule4_assert_no_secrets_raises():
    """Verify that unredacted secrets trigger SecretLeakageError."""
    dirty_prompt = 'Analyze this bug. My key is sk-ant-secret12345678901234567890.'
    with pytest.raises(SecretLeakageError) as exc_info:
        assert_clean_prompt(dirty_prompt)
    assert "Unredacted secret detected before LLM ingestion" in str(exc_info.value)
