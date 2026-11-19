from __future__ import annotations

import json
import pytest
import httpx

from autopatch.git.github_client import GitHubClient, GitHubTokenMissingError, GitHubApiError


@pytest.mark.anyio
async def test_missing_token_raises_clear_error():
    """Verify that calling GitHubClient without a token raises GitHubTokenMissingError with a helpful message."""
    client = GitHubClient(token="")
    with pytest.raises(GitHubTokenMissingError) as exc_info:
        await client.open_pull_request(
            repo_slug="acme/service",
            head_branch="autopatch/fix",
            base_branch="main",
            title="AutoPatch Fix",
            body_markdown="# Report",
        )
    assert "GitHub API token is missing" in str(exc_info.value)
    assert "GITHUB_TOKEN" in str(exc_info.value)


@pytest.mark.anyio
async def test_open_pull_request_success():
    """Verify opening pull request via mock HTTP transport returns PullRequestResult."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/repos/octocat/hello-world/pulls"
        assert request.headers["authorization"] == "Bearer mock_token_123"
        payload = json.loads(request.content)
        assert payload["title"] == "[AutoPatch] Verified Fixes"
        assert payload["head"] == "autopatch/fix-branch"
        assert payload["base"] == "main"
        return httpx.Response(
            201,
            json={
                "number": 42,
                "html_url": "https://github.com/octocat/hello-world/pull/42",
                "commits": 2,
            },
        )

    transport = httpx.MockTransport(handler)
    client = GitHubClient(token="mock_token_123", transport=transport)

    result = await client.open_pull_request(
        repo_slug="octocat/hello-world",
        head_branch="autopatch/fix-branch",
        base_branch="main",
        title="[AutoPatch] Verified Fixes",
        body_markdown="# PR Evidence Table",
    )

    assert result.pr_number == 42
    assert result.html_url == "https://github.com/octocat/hello-world/pull/42"
    assert result.head_branch == "autopatch/fix-branch"
    assert result.commits_count == 2


@pytest.mark.anyio
async def test_github_api_error_handling():
    """Verify that API errors (e.g. 403 Forbidden or 422 Unprocessable) raise GitHubApiError with status code."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"message": "A pull request already exists for this head branch.", "documentation_url": "https://docs.github.com"},
        )

    transport = httpx.MockTransport(handler)
    client = GitHubClient(token="mock_token_123", transport=transport)

    with pytest.raises(GitHubApiError) as exc_info:
        await client.open_pull_request(
            repo_slug="octocat/hello-world",
            head_branch="autopatch/fix-branch",
            base_branch="main",
            title="[AutoPatch] Verified Fixes",
            body_markdown="# PR Evidence Table",
        )
    assert exc_info.value.status_code == 422
    assert "A pull request already exists" in str(exc_info.value)
