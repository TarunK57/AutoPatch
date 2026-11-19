from __future__ import annotations

import pytest
from autopatch.core.exceptions import SecretLeakageError
from autopatch.security.redaction import SecretRedactor, assert_clean_prompt, redact_secrets


def test_comprehensive_secret_redaction():
    """Verify that all major secret types are redacted and masked with typed placeholders."""
    redactor = SecretRedactor()

    raw_code = (
        '# Configuration file\n'
        'OPENAI_API_KEY = "sk-proj-abc1234567890abcdef1234567890"\n'
        'ANTHROPIC_KEY = "sk-ant-api03-abcdef1234567890abcdef1234567890"\n'
        'AWS_ACCESS = "AKIA1234567890ABCDEF"\n'
        'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n'
        'GITHUB_TOKEN = "ghp_1234567890abcdef1234567890abcdef1234"\n'
        'SLACK_BOT = "xoxb-123456789012-1234567890123-abcdef123456"\n'
        'DATABASE_URL = "postgres://admin:SuperSecretPass123!@db.internal:5432/production"\n'
        'user_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature"\n'
        'password = "MyComplexPassword#99"\n'
    )

    sanitized, matches = redactor.redact(raw_code)

    # 1. Assert no raw secrets exist in the sanitized text
    assert "sk-proj-" not in sanitized
    assert "sk-ant-" not in sanitized
    assert "AKIA1234567890ABCDEF" not in sanitized
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in sanitized
    assert "ghp_1234567890" not in sanitized
    assert "xoxb-" not in sanitized
    assert "SuperSecretPass123!" not in sanitized
    assert "MyComplexPassword#99" not in sanitized

    # 2. Assert placeholders exist
    assert "[REDACTED_OPENAI_KEY_" in sanitized
    assert "[REDACTED_ANTHROPIC_KEY_" in sanitized
    assert "[REDACTED_AWS_ACCESS_KEY_" in sanitized
    assert "[REDACTED_AWS_SECRET_KEY_" in sanitized
    assert "[REDACTED_GITHUB_TOKEN_" in sanitized
    assert "[REDACTED_SLACK_TOKEN_" in sanitized
    assert "[REDACTED_DATABASE_URI_" in sanitized
    assert "[REDACTED_CREDENTIAL_" in sanitized

    # 3. Assert assert_clean_prompt passes on sanitized text
    redactor.assert_no_secrets(sanitized)

    # 4. Invertible restoration: assert original text can be restored byte-for-byte
    restored = redactor.restore(sanitized)
    assert restored == raw_code


def test_assert_clean_prompt_raises_on_unredacted_secret():
    """Verify that assert_no_secrets raises SecretLeakageError when raw secrets exist in prompt."""
    redactor = SecretRedactor()

    leak_prompt = "Here is the code to review:\nAKIAIOSFODNN7EXAMPLE = 'access'"
    with pytest.raises(SecretLeakageError) as exc_info:
        redactor.assert_no_secrets(leak_prompt)

    assert "Unredacted secret detected" in str(exc_info.value)
    assert "AWS_ACCESS_KEY" in str(exc_info.value)
