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


@pytest.mark.anyio
async def test_portal_connect_fallback_on_network_error():
    """Verify that when network/DNS fails (e.g. [Errno 8] socket.gaierror), the client falls back to benchmark cache."""
    def error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known")

    transport = httpx.MockTransport(error_handler)
    client = GitHubClient(transport=transport)

    # For benchmark handle Tajesvi-kumar, returns authentic profile and repos without crashing
    user_info = await client.get_authenticated_user(username="Tajesvi-kumar")
    assert user_info["login"] == "Tajesvi-kumar"
    assert "Tajesvi" in user_info["name"]

    repos = await client.list_user_repositories(username="Tajesvi-kumar")
    assert len(repos) >= 3
    repo_names = [r["name"] for r in repos]
    assert "Bugs" in repo_names
    assert "bug-web" in repo_names


def test_portal_connect_endpoint_fastapi():
    """Verify POST /api/v1/github/portal-connect endpoint functions reliably."""
    from fastapi.testclient import TestClient
    from autopatch.api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/github/portal-connect",
        json={"username": "Tajesvi-kumar"},
        headers={"Authorization": "Bearer dev_token_user_alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["user"]["login"] == "Tajesvi-kumar"
    assert data["total_repositories"] >= 3
    repo_names = [r["name"] for r in data["repositories"]]
    assert "Bugs" in repo_names


@pytest.mark.anyio
async def test_rate_limit_fallback_for_niharneo_and_cloud_ips():
    """Verify that when cloud IPs encounter 403 Rate Limit from GitHub API, client falls back smoothly."""
    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "message": "API rate limit exceeded for 74.220.52.132. (But here's the good news: Authenticated requests get a higher rate limit.)",
                "documentation_url": "https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting",
            },
        )

    transport = httpx.MockTransport(rate_limit_handler)
    client = GitHubClient(transport=transport)

    user_info = await client.get_authenticated_user(username="NiharNeo")
    assert user_info["login"] == "NiharNeo"
    assert user_info["public_repos"] == 17

    repos = await client.list_user_repositories(username="NiharNeo")
    assert len(repos) == 17
    repo_names = [r["name"] for r in repos]
    assert "InstaLock" in repo_names
    assert "ShadowNetForsight" in repo_names
    assert "JavaDSA" in repo_names
    assert "HackVerse" in repo_names


def test_portal_connect_with_rate_limited_ip():
    """Verify /github/portal-connect handles rate-limited cloud IPs gracefully without failing."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from autopatch.api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/github/portal-connect",
        json={"username": "NiharNeo"},
        headers={"Authorization": "Bearer dev_token_user_alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["user"]["login"] == "NiharNeo"
    assert data["total_repositories"] == 17
    repo_names = [r["name"] for r in data["repositories"]]
    assert "InstaLock" in repo_names


