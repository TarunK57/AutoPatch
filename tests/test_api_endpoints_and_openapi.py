"""Unit tests verifying FastAPI endpoints, OpenAPI schema completeness, cross-user isolation, and human decision invariants."""

import io
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from autopatch.api.main import app
from autopatch.api.routes import PROJECTS_DB, JOBS_DB
from autopatch.api.rate_limit import default_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    PROJECTS_DB.clear()
    JOBS_DB.clear()
    default_rate_limiter.reset()


def test_openapi_docs_complete():
    """Acceptance criterion: OpenAPI docs complete and schema fully described."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    assert schema["info"]["title"] == "AutoPatch API"
    assert schema["info"]["version"] == "1.0.0"
    paths = schema["paths"]

    # Assert key required endpoints are documented
    assert "/api/v1/projects" in paths
    assert "/api/v1/projects/{project_id}/scan" in paths
    assert "/api/v1/jobs/{job_id}" in paths
    assert "/api/v1/jobs/{job_id}/events" in paths
    assert "/api/v1/projects/{project_id}/bugs" in paths
    assert "/api/v1/projects/{project_id}/bugs/{bug_id}" in paths
    assert "/api/v1/projects/{project_id}/bugs/{bug_id}/decision" in paths
    assert "/api/v1/projects/{project_id}/bugs/{bug_id}/revert" in paths
    assert "/api/v1/projects/{project_id}/export" in paths
    assert "/api/v1/projects/{project_id}/history" in paths


def test_cross_user_access_attempts_fail():
    """Acceptance criterion: Cross-user access attempts strictly fail with 403 Forbidden."""
    headers_alice = {"Authorization": "Bearer dev_token_user_alice"}
    headers_bob = {"Authorization": "Bearer dev_token_user_bob"}

    # 1. User Alice creates a project
    create_res = client.post(
        "/api/v1/projects",
        json={"name": "Alice Secret Project"},
        headers=headers_alice,
    )
    assert create_res.status_code == 201
    proj_id = create_res.json()["project_id"]

    # 2. User Bob attempts to access Alice's project -> 403 Forbidden
    get_res = client.get(
        f"/api/v1/projects/{proj_id}/bugs",
        headers=headers_bob,
    )
    assert get_res.status_code == 403
    assert "Cross-user access forbidden" in get_res.json()["detail"]

    # 3. User Bob attempts to scan Alice's project -> 403 Forbidden
    scan_res = client.post(
        f"/api/v1/projects/{proj_id}/scan",
        json={},
        headers=headers_bob,
    )
    assert scan_res.status_code == 403

    # 4. Unauthenticated request -> 401 Unauthorized
    unauth_res = client.get(f"/api/v1/projects/{proj_id}/bugs")
    assert unauth_res.status_code == 401


def test_create_project_with_zip_upload_and_scanning():
    """Validates zip upload ingestion, scanning, and project creation."""
    headers = {"Authorization": "Bearer dev_token_user_alice"}

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("src/calc.py", "def add(a, b): return a + b\n")
        zf.writestr("tests/test_calc.py", "def test_add(): assert add(1, 2) == 3\n")
    zip_bytes = zip_buffer.getvalue()

    response = client.post(
        "/api/v1/projects",
        data={"name": "Calc Project"},
        files={"file": ("calc.zip", zip_bytes, "application/zip")},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Calc Project"
    assert data["owner_id"] == "user_alice"
    assert data["total_files"] >= 2


def test_decision_accept_applies_patch_and_revert():
    """Enforces Rule 1 (Trust): patch is applied ONLY on human approval, and can be cleanly reverted."""
    headers = {"Authorization": "Bearer dev_token_user_alice"}

    # 1. Create project with a target file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("src/service.py", "def serve(): return 'old_value'\n")
    response = client.post(
        "/api/v1/projects",
        data={"name": "Service Project"},
        files={"file": ("service.zip", zip_buffer.getvalue(), "application/zip")},
        headers=headers,
    )
    proj_id = response.json()["project_id"]

    # 2. Seed a bug and patch in event store
    from autopatch.api.routes import event_store
    from autopatch.orchestrator.events import AuditEvent, EventType

    bug_id = f"job-123:src/service.py:1"
    event_store.append(
        AuditEvent(
            job_id="job-123",
            bug_id=bug_id,
            event_type=EventType.BUG_PIPELINE_STARTED,
            payload={"finding": {"file": "src/service.py", "line_start": 1}},
        )
    )
    event_store.append(
        AuditEvent(
            job_id="job-123",
            bug_id=bug_id,
            event_type=EventType.PATCHER_COMPLETED,
            payload={
                "candidate_patches": [
                    {
                        "id": "patch-1",
                        "file": "src/service.py",
                        "original_snippet": "return 'old_value'",
                        "patched_snippet": "return 'new_verified_value'",
                        "unified_diff": "--- a/src/service.py\n+++ b/src/service.py\n@@ -1 +1 @@\n-def serve(): return 'old_value'\n+def serve(): return 'new_verified_value'\n",
                        "rationale": "Updated return value",
                    }
                ]
            },
        )
    )
    event_store.append(
        AuditEvent(
            job_id="job-123",
            bug_id=bug_id,
            event_type=EventType.BUG_COMPLETED,
            payload={"status": "COMPLETED"},
        )
    )

    # 3. Human Approval Decision
    decision_res = client.post(
        f"/api/v1/projects/{proj_id}/bugs/{bug_id}/decision",
        json={"decision": "APPROVED", "comment": "Verified and looks great!"},
        headers=headers,
    )
    assert decision_res.status_code == 200
    dec_data = decision_res.json()
    assert dec_data["status"] == "APPROVED"
    assert dec_data["applied"] is True
    assert len(dec_data["signature_hash"]) > 20

    # Verify file was updated on disk
    proj_record = PROJECTS_DB[proj_id]
    target_content = (Path(proj_record["project_dir"]) / "src/service.py").read_text()
    assert "return 'new_verified_value'" in target_content

    # 4. Revert Decision
    revert_res = client.post(
        f"/api/v1/projects/{proj_id}/bugs/{bug_id}/revert",
        headers=headers,
    )
    assert revert_res.status_code == 200
    revert_data = revert_res.json()
    assert revert_data["reverted"] is True

    # Verify file was restored to original
    target_content_after = (Path(proj_record["project_dir"]) / "src/service.py").read_text()
    assert "return 'old_value'" in target_content_after


def test_export_formats():
    """Validates export endpoints (diff, markdown, sarif, zip)."""
    headers = {"Authorization": "Bearer dev_token_user_alice"}

    create_res = client.post(
        "/api/v1/projects",
        json={"name": "Export Project"},
        headers=headers,
    )
    proj_id = create_res.json()["project_id"]

    # 1. Export Diff
    diff_res = client.get(f"/api/v1/projects/{proj_id}/export?format=diff", headers=headers)
    assert diff_res.status_code == 200
    assert "text/x-diff" in diff_res.headers["content-type"]

    # 2. Export Markdown
    md_res = client.get(f"/api/v1/projects/{proj_id}/export?format=markdown", headers=headers)
    assert md_res.status_code == 200
    assert "# AutoPatch Autonomous Repair Report" in md_res.text

    # 3. Export SARIF
    sarif_res = client.get(f"/api/v1/projects/{proj_id}/export?format=sarif", headers=headers)
    assert sarif_res.status_code == 200
    sarif_data = sarif_res.json()
    assert sarif_data["version"] == "2.1.0"
    assert sarif_data["runs"][0]["tool"]["driver"]["name"] == "AutoPatch"

    # 4. Export ZIP
    zip_res = client.get(f"/api/v1/projects/{proj_id}/export?format=zip", headers=headers)
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"


def test_git_branch_and_pr_endpoints():
    """Validates FastAPI Git remediation branch and pull request endpoints."""
    headers = {"Authorization": "Bearer dev_token_user_alice"}

    create_res = client.post(
        "/api/v1/projects",
        json={"name": "Git Test Project"},
        headers=headers,
    )
    proj_id = create_res.json()["project_id"]

    # 1. Create remediation branch endpoint
    branch_res = client.post(
        f"/api/v1/projects/{proj_id}/git/branch",
        json={
            "branch_name": "autopatch/verified-fixes",
            "base_branch": "main",
            "include_brt_tests": True,
        },
        headers=headers,
    )
    assert branch_res.status_code == 200
    b_data = branch_res.json()
    assert b_data["branch_name"] == "autopatch/verified-fixes"
    assert b_data["base_branch"] == "main"
    assert "total_commits" in b_data

    # 2. Open Pull Request endpoint - missing token returns 401
    pr_unauth = client.post(
        f"/api/v1/projects/{proj_id}/git/pull-request",
        json={
            "repo_slug": "acme/repo",
            "head_branch": "autopatch/verified-fixes",
            "base_branch": "main",
        },
        headers=headers,
    )
    assert pr_unauth.status_code == 401
    assert "GitHub API token is missing" in pr_unauth.json()["detail"]

