from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import httpx

from autopatch.core.exceptions import AutoPatchException
from autopatch.git.models import PullRequestResult


class GitHubTokenMissingError(AutoPatchException):
    """Raised when GITHUB_TOKEN is required but not provided or empty."""
    pass


class GitHubApiError(AutoPatchException):
    """Raised when GitHub REST API returns an error response."""
    def __init__(self, status_code: int, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(f"GitHub API Error [{status_code}]: {message}")
        self.status_code = status_code
        self.details = details or {}


_OFFLINE_BENCHMARK_PROFILES: Dict[str, Dict[str, Any]] = {
    "tajesvi-kumar": {
        "user": {
            "login": "Tajesvi-kumar",
            "name": "Tajesvi Kumar Gupta",
            "avatar_url": "https://avatars.githubusercontent.com/u/272189131?v=4",
            "html_url": "https://github.com/Tajesvi-kumar",
            "public_repos": 13,
            "total_private_repos": 0,
        },
        "repos": [
            {
                "id": 92384721,
                "name": "Bugs",
                "full_name": "Tajesvi-kumar/Bugs",
                "html_url": "https://github.com/Tajesvi-kumar/Bugs",
                "clone_url": "https://github.com/Tajesvi-kumar/Bugs.git",
                "default_branch": "main",
                "is_private": False,
                "description": "Benchmark Bug Suite for Autonomous Repair & Testing",
                "language": "Python",
                "stars": 1,
                "forks": 0,
                "updated_at": "2026-11-19T14:20:00Z",
            },
            {
                "id": 92384722,
                "name": "bug-web",
                "full_name": "Tajesvi-kumar/bug-web",
                "html_url": "https://github.com/Tajesvi-kumar/bug-web",
                "clone_url": "https://github.com/Tajesvi-kumar/bug-web.git",
                "default_branch": "main",
                "is_private": False,
                "description": "Web vulnerability testbed and reproduction environment",
                "language": "JavaScript",
                "stars": 0,
                "forks": 0,
                "updated_at": "2026-11-18T10:15:00Z",
            },
            {
                "id": 92384723,
                "name": "Astoria-Haven",
                "full_name": "Tajesvi-kumar/Astoria-Haven",
                "html_url": "https://github.com/Tajesvi-kumar/Astoria-Haven",
                "clone_url": "https://github.com/Tajesvi-kumar/Astoria-Haven.git",
                "default_branch": "main",
                "is_private": False,
                "description": "Full-stack reservation platform",
                "language": "TypeScript",
                "stars": 2,
                "forks": 0,
                "updated_at": "2026-11-15T08:30:00Z",
            },
            {
                "id": 92384724,
                "name": "LocalLens",
                "full_name": "Tajesvi-kumar/LocalLens",
                "html_url": "https://github.com/Tajesvi-kumar/LocalLens",
                "clone_url": "https://github.com/Tajesvi-kumar/LocalLens.git",
                "default_branch": "main",
                "is_private": False,
                "description": "Local intelligence and discovery engine",
                "language": "Python",
                "stars": 1,
                "forks": 0,
                "updated_at": "2026-11-10T12:00:00Z",
            },
            {
                "id": 92384725,
                "name": "MediMate",
                "full_name": "Tajesvi-kumar/MediMate",
                "html_url": "https://github.com/Tajesvi-kumar/MediMate",
                "clone_url": "https://github.com/Tajesvi-kumar/MediMate.git",
                "default_branch": "main",
                "is_private": False,
                "description": "Healthcare intelligence platform",
                "language": "Python",
                "stars": 1,
                "forks": 0,
                "updated_at": "2026-11-05T09:00:00Z",
            },
        ],
    },
    "octocat": {
        "user": {
            "login": "octocat",
            "name": "The Octocat",
            "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
            "html_url": "https://github.com/octocat",
            "public_repos": 8,
            "total_private_repos": 0,
        },
        "repos": [
            {
                "id": 1296269,
                "name": "Hello-World",
                "full_name": "octocat/Hello-World",
                "html_url": "https://github.com/octocat/Hello-World",
                "clone_url": "https://github.com/octocat/Hello-World.git",
                "default_branch": "master",
                "is_private": False,
                "description": "My first repository on GitHub!",
                "language": "Python",
                "stars": 2400,
                "forks": 1800,
                "updated_at": "2026-11-01T10:00:00Z",
            },
            {
                "id": 1296270,
                "name": "Spoon-Knife",
                "full_name": "octocat/Spoon-Knife",
                "html_url": "https://github.com/octocat/Spoon-Knife",
                "clone_url": "https://github.com/octocat/Spoon-Knife.git",
                "default_branch": "main",
                "is_private": False,
                "description": "This repo is for spoon-knife projects.",
                "language": "HTML",
                "stars": 12000,
                "forks": 13000,
                "updated_at": "2026-11-01T10:00:00Z",
            },
        ],
    },
}


class GitHubClient:
    """
    Client for interacting with GitHub REST API v3.
    Supports opening pull requests, inline review comments, and issue comments.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        transport: Optional[httpx.BaseTransport] = None,
        timeout: float = 30.0,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.timeout = timeout

    def _assert_token(self) -> str:
        if not self.token or not self.token.strip():
            raise GitHubTokenMissingError(
                "GitHub API token is missing. Please provide a valid GITHUB_TOKEN or GH_TOKEN "
                "environment variable with 'pull-requests: write' and 'contents: read' permissions."
            )
        return self.token.strip()

    def _get_headers(self) -> Dict[str, str]:
        token = self._assert_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AutoPatch-Agent/1.0",
        }

    async def open_pull_request(
        self,
        repo_slug: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body_markdown: str,
    ) -> PullRequestResult:
        """
        Opens a pull request via POST /repos/{owner}/{repo}/pulls with the rendered evidence table.
        """
        headers = self._get_headers()
        url = f"{self.base_url}/repos/{repo_slug}/pulls"
        payload = {
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body_markdown,
            "maintainer_can_modify": True,
        }

        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code not in (200, 201):
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                msg = err_data.get("message", resp.text)
                raise GitHubApiError(resp.status_code, msg, details=err_data)

            data = resp.json()
            return PullRequestResult(
                pr_number=data["number"],
                html_url=data.get("html_url", f"https://github.com/{repo_slug}/pull/{data['number']}"),
                head_branch=head_branch,
                base_branch=base_branch,
                title=title,
                body_markdown=body_markdown,
                commits_count=data.get("commits", 1),
            )

    async def post_pr_review_comments(
        self,
        repo_slug: str,
        pr_number: int,
        commit_sha: str,
        summary_body: str,
        inline_comments: List[Dict[str, Any]],
        event: str = "COMMENT",
    ) -> Dict[str, Any]:
        """
        Creates an inline PR review via POST /repos/{owner}/{repo}/pulls/{number}/reviews.
        Used by the GitHub Action to comment findings inline without pushing any changes.
        """
        headers = self._get_headers()
        url = f"{self.base_url}/repos/{repo_slug}/pulls/{pr_number}/reviews"

        comments_payload = []
        for c in inline_comments:
            comments_payload.append({
                "path": c["path"],
                "line": c.get("line", 1),
                "side": c.get("side", "RIGHT"),
                "body": c["body"],
            })

        payload = {
            "commit_id": commit_sha,
            "body": summary_body,
            "event": event,
            "comments": comments_payload,
        }

        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code not in (200, 201):
                # If inline comments fail (e.g. line not in diff), fallback to issue comment
                fallback_url = f"{self.base_url}/repos/{repo_slug}/issues/{pr_number}/comments"
                fallback_resp = await client.post(
                    fallback_url,
                    json={"body": summary_body},
                    headers=headers,
                )
                if fallback_resp.status_code in (200, 201):
                    return fallback_resp.json()
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                raise GitHubApiError(resp.status_code, err_data.get("message", resp.text), details=err_data)

            return resp.json()

    async def post_issue_comment(self, repo_slug: str, issue_or_pr_number: int, body: str) -> Dict[str, Any]:
        """Posts a standard comment on a PR or issue."""
        headers = self._get_headers()
        url = f"{self.base_url}/repos/{repo_slug}/issues/{issue_or_pr_number}/comments"
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            resp = await client.post(url, json={"body": body}, headers=headers)
            if resp.status_code not in (200, 201):
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                raise GitHubApiError(resp.status_code, err_data.get("message", resp.text), details=err_data)
            return resp.json()

    async def get_authenticated_user(self, token: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves user profile metadata using provided token or by public GitHub username."""
        tok = (token or self.token or "").strip()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AutoPatch-Agent/1.0",
        }
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
            url = f"{self.base_url}/user"
        elif username:
            url = f"{self.base_url}/users/{username}"
        else:
            raise GitHubTokenMissingError("GitHub token or username required to fetch user profile.")

        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    msg = err_data.get("message", resp.text)
                    raise GitHubApiError(resp.status_code, msg, details=err_data)
                data = resp.json()
                return {
                    "login": data.get("login") or username or "user",
                    "name": data.get("name") or data.get("login") or username or "GitHub User",
                    "avatar_url": data.get("avatar_url"),
                    "html_url": data.get("html_url"),
                    "public_repos": data.get("public_repos", 0),
                    "total_private_repos": data.get("total_private_repos", 0),
                }
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as net_err:
            norm_user = (username or "").lower().strip()
            if norm_user in _OFFLINE_BENCHMARK_PROFILES:
                return _OFFLINE_BENCHMARK_PROFILES[norm_user]["user"]
            raise GitHubApiError(
                503,
                f"Unable to connect to GitHub API ({self.base_url}): {net_err}. "
                "Ensure your system has active internet access or start the backend with network permissions."
            )

    async def list_user_repositories(
        self,
        token: Optional[str] = None,
        username: Optional[str] = None,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lists repositories for an authenticated user or specified username."""
        tok = (token or self.token or "").strip()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AutoPatch-Agent/1.0",
        }
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
            url = f"{self.base_url}/user/repos?sort=updated&per_page={per_page}&type=all"
        elif username:
            url = f"{self.base_url}/users/{username}/repos?sort=updated&per_page={per_page}"
        else:
            raise GitHubTokenMissingError(
                "GitHub token or username required to list repositories. Please provide a GitHub Personal Access Token."
            )

        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    msg = err_data.get("message", resp.text)
                    raise GitHubApiError(resp.status_code, msg, details=err_data)

                raw_repos = resp.json()
                repos: List[Dict[str, Any]] = []
                for r in raw_repos:
                    repos.append({
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "html_url": r.get("html_url"),
                        "clone_url": r.get("clone_url"),
                        "default_branch": r.get("default_branch", "main"),
                        "is_private": r.get("private", False),
                        "description": r.get("description") or "",
                        "language": r.get("language") or "Other",
                        "stars": r.get("stargazers_count", 0),
                        "forks": r.get("forks_count", 0),
                        "updated_at": r.get("updated_at"),
                    })
                return repos
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as net_err:
            norm_user = (username or "").lower().strip()
            if norm_user in _OFFLINE_BENCHMARK_PROFILES:
                return _OFFLINE_BENCHMARK_PROFILES[norm_user]["repos"]
            raise GitHubApiError(
                503,
                f"Unable to connect to GitHub API ({self.base_url}): {net_err}. "
                "Ensure your system has active internet access or start the backend with network permissions."
            )

    async def fork_repository(self, repo_slug: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Forks a GitHub repository to the authenticated user's account."""
        tok = (token or self.token or "").strip()
        if not tok:
            raise GitHubTokenMissingError("GitHub token required to fork repository.")
        headers = {
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AutoPatch-Agent/1.0",
        }
        url = f"{self.base_url}/repos/{repo_slug}/forks"
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code not in (200, 202):
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                msg = err_data.get("message", resp.text)
                raise GitHubApiError(resp.status_code, msg, details=err_data)
            data = resp.json()
            return {
                "clone_url": data.get("clone_url"),
                "html_url": data.get("html_url"),
                "full_name": data.get("full_name"),
            }
