"""Unit and integration tests for the live Health & Observability Dashboard endpoint."""

import pytest
from fastapi.testclient import TestClient
from autopatch.api.main import app

client = TestClient(app)
AUTH_HEADER = {"Authorization": "Bearer dev_token_user_developer"}


def test_dashboard_endpoint_returns_real_telemetry():
    """Validates that GET /api/v1/observability/dashboard returns real structured telemetry."""
    resp = client.get("/api/v1/observability/dashboard", headers=AUTH_HEADER)
    assert resp.status_code == 200, f"Expected 200 OK, got: {resp.text}"
    data = resp.json()

    # Check top-level schema
    assert "kpis" in data
    assert "cwe_distribution" in data
    assert "velocity_curve" in data
    assert "recent_activities" in data
    assert "projects_list" in data

    kpis = data["kpis"]
    assert isinstance(kpis["verification_rate"], (int, float))
    assert isinstance(kpis["mttr_seconds"], (int, float))
    assert isinstance(kpis["mttr_display"], str)
    assert isinstance(kpis["vulnerabilities_resolved"], int)
    assert isinstance(kpis["vulnerabilities_total"], int)
    assert isinstance(kpis["patches_applied"], int)
    assert isinstance(kpis["total_audit_events"], int)
    assert isinstance(kpis["total_projects"], int)
    assert isinstance(kpis["total_tokens"], int)
    assert isinstance(kpis["total_cost_usd"], (int, float))

    # Velocity curve
    vel = data["velocity_curve"]
    assert "unit" in vel
    assert isinstance(vel["points"], list)
    for pt in vel["points"]:
        assert "label" in pt
        assert "count" in pt

    # CWE distribution
    cwe_list = data["cwe_distribution"]
    assert isinstance(cwe_list, list)
    for it in cwe_list:
        assert "key" in it
        assert "label" in it
        assert "count" in it
        assert "percentage" in it
        assert "color" in it

    # Action ledger
    acts = data["recent_activities"]
    assert isinstance(acts, list)
    for act in acts:
        assert "event_id" in act
        assert "job_id" in act
        assert "event_type" in act
        assert "actor" in act
        assert "timestamp" in act
        assert "time_ago" in act
        assert "title" in act
        assert "description" in act
        assert "badge_type" in act


def test_dashboard_endpoint_with_project_filter():
    """Validates project-specific filtering on the dashboard endpoint."""
    # List projects to get an ID
    p_resp = client.get("/api/v1/projects", headers=AUTH_HEADER)
    assert p_resp.status_code == 200
    projs = p_resp.json()

    if projs:
        target_pid = projs[0]["project_id"]
        target_name = projs[0]["name"]

        resp = client.get(
            f"/api/v1/observability/dashboard?project_id={target_pid}",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == target_pid
        assert data["project_name"] == target_name
        assert "kpis" in data
