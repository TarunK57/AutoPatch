"""Unit tests for interactive HTML report generation, multi-format export, and git clone ingestion."""

from pathlib import Path
from typing import Dict, Any, List
import pytest
from fastapi.testclient import TestClient

from autopatch.api.main import app
from autopatch.api.export import ProjectExporter
from autopatch.ingestion.extractor import SafeExtractor, IngestionError


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_bug_items() -> List[Dict[str, Any]]:
    return [
        {
            "bug_id": "proj-1:math.py:12",
            "file_path": "src/math.py",
            "line_start": 12,
            "description": "Potential off-by-one boundary flaw in loop indexing",
            "status": "COMPLETED",
            "rank": 1,
            "finding": {
                "file": "src/math.py",
                "line_start": 12,
                "category": "boundary",
                "description": "Potential off-by-one boundary flaw in loop indexing",
            },
            "priority": {
                "priority_score": 88.5,
                "rank": 1,
                "severity": {"severity_level": "HIGH", "numeric_severity": 0.8},
                "confidence": {"overall_confidence": 0.95},
            },
            "root_cause": {
                "summary": "Loop upper bound uses <= instead of < causing IndexError.",
                "causal_chain": ["caller -> loop -> index out of range"],
            },
            "verification": {
                "is_verified": True,
                "regression_count": 0,
            },
            "patches": [
                {
                    "patch_id": "patch-1",
                    "file": "src/math.py",
                    "original_snippet": "for i in range(len(arr) + 1):",
                    "patched_snippet": "for i in range(len(arr)):",
                    "unified_diff": "--- a/src/math.py\n+++ b/src/math.py\n-for i in range(len(arr) + 1):\n+for i in range(len(arr)):",
                    "rationale": "Corrected off-by-one upper range limit.",
                    "confidence": 0.95,
                    "strategy": "TEMPLATE_OFF_BY_ONE",
                }
            ],
        }
    ]


def test_export_interactive_html_report(sample_bug_items):
    """Verify HTML report includes KPIs, diffs, and severity badges."""
    html = ProjectExporter.export_interactive_html_report("TestProject", sample_bug_items)

    assert "<!DOCTYPE html>" in html
    assert "AutoPatch Autonomous Remediation Dossier" in html
    assert "TestProject" in html
    assert "Total Defects Identified" in html
    assert "src/math.py:12" in html
    assert "diff-add" in html
    assert "diff-del" in html
    assert "for i in range(len(arr))" in html
    assert "Print / Save PDF" in html


def test_api_report_endpoint_html(client: TestClient, sample_bug_items, monkeypatch):
    """Verify GET /api/v1/projects/{id}/report returns HTML report."""
    from autopatch.api.routes import PROJECTS_DB, event_store, EventStore
    from autopatch.orchestrator.events import AuditEvent, EventType

    proj_id = "test-proj-report-1"
    PROJECTS_DB[proj_id] = {
        "project_id": proj_id,
        "name": "AuditProject",
        "owner_id": "user_developer",
        "project_dir": "/tmp",
        "total_files": 5,
        "languages": ["Python"],
        "applied_patches": {},
    }

    # Add mock event for bug state
    event_store.append(
        AuditEvent(
            job_id="job-report-1",
            bug_id=sample_bug_items[0]["bug_id"],
            event_type=EventType.BUG_PIPELINE_STARTED,
            actor="ORCHESTRATOR",
            payload={"finding": sample_bug_items[0]["finding"]},
        )
    )

    headers = {"Authorization": "Bearer dev_token_user_developer"}
    res = client.get(f"/api/v1/projects/{proj_id}/report?format=html", headers=headers)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "<!DOCTYPE html>" in res.text
    assert "AuditProject" in res.text


def test_api_export_json_format(client: TestClient):
    """Verify GET /api/v1/projects/{id}/export?format=json returns JSON."""
    from autopatch.api.routes import PROJECTS_DB

    proj_id = "test-proj-json-1"
    PROJECTS_DB[proj_id] = {
        "project_id": proj_id,
        "name": "JsonAuditProject",
        "owner_id": "user_developer",
        "project_dir": "/tmp",
        "total_files": 3,
        "languages": ["Python"],
        "applied_patches": {},
    }

    headers = {"Authorization": "Bearer dev_token_user_developer"}
    res = client.get(f"/api/v1/projects/{proj_id}/export?format=json", headers=headers)
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert data["project_id"] == proj_id
    assert "total_bugs" in data


def test_safe_extractor_rejects_malicious_git_url(tmp_path: Path):
    """Verify clone_git_repo rejects argument injection and illegal characters."""
    extractor = SafeExtractor()
    dest = tmp_path / "target"

    with pytest.raises(IngestionError) as exc_1:
        extractor.clone_git_repo("--upload-pack=evil", dest)
    assert "cannot start with a dash" in str(exc_1.value)

    with pytest.raises(IngestionError) as exc_2:
        extractor.clone_git_repo("https://github.com/foo/bar; rm -rf /", dest)
    assert "illegal characters" in str(exc_2.value)
