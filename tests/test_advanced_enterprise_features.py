"""Comprehensive test suite for the 7 new advanced enterprise features:
1. Predictive Bug Detection
2. Code Hotspot Detection
3. AI Model Committee (Separate Mode)
4. Long-term Learning from Repairs
5. API Security Testing
6. Bug Origin Detection
7. Automatic Documentation
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from autopatch.api.main import app
from autopatch.detection.predictive import PredictiveDetector
from autopatch.intelligence.hotspots import CodeHotspotAnalyzer
from autopatch.intelligence.committee import ModelCommitteeOrchestrator
from autopatch.storage.repair_memory import RepairMemoryStore
from autopatch.security.api_security import ApiSecurityScanner
from autopatch.git.origin_tracker import BugOriginTracker
from autopatch.intelligence.documentation import AutoDocumentationGenerator

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev_token_user_developer"}


@pytest.fixture
def target_project_id():
    resp = client.get("/api/v1/projects", headers=AUTH)
    assert resp.status_code == 200
    projs = resp.json()
    if projs:
        return projs[0]["project_id"]
    return "test-proj-fallback"


# ============================================================================
# 1. Predictive Bug Detection
# ============================================================================

def test_predictive_bug_detection_direct(tmp_path: Path):
    """Direct detector test finding mutable defaults and bare exceptions."""
    bad_file = tmp_path / "vulnerable_service.py"
    bad_file.write_text(
        "def bad_function(items=[]):\n"
        "    try:\n"
        "        x = items.get('key')\n"
        "        print(x.name)\n"
        "    except:\n"
        "        pass\n",
        encoding="utf-8"
    )

    detector = PredictiveDetector()
    findings = detector.detect(tmp_path, [])
    assert len(findings) >= 2
    types = [f.metadata.get("hazard_type") for f in findings]
    assert "MUTABLE_DEFAULT_ARG" in types
    assert "BARE_EXCEPTION_SUPPRESSION" in types


def test_predictive_bug_detection_endpoint(target_project_id: str):
    """Tests the REST endpoint GET /projects/{id}/predictive-analysis."""
    resp = client.get(f"/api/v1/projects/{target_project_id}/predictive-analysis", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_hazards_predicted" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)


# ============================================================================
# 2. Code Hotspot Detection
# ============================================================================

def test_code_hotspot_detection_direct(tmp_path: Path):
    """Direct test analyzing churn and complexity on source files."""
    code_file = tmp_path / "core_logic.py"
    code_file.write_text("\n".join(f"x = {i}" for i in range(150)), encoding="utf-8")

    analyzer = CodeHotspotAnalyzer(tmp_path)
    report = analyzer.analyze_hotspots("proj-1")
    assert report.total_files_analyzed >= 1
    assert len(report.hotspots) >= 1
    assert report.hotspots[0].hotspot_score >= 0.0


def test_code_hotspot_detection_endpoint(target_project_id: str):
    """Tests the REST endpoint GET /projects/{id}/hotspots."""
    resp = client.get(f"/api/v1/projects/{target_project_id}/hotspots?max_results=10", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_files_analyzed" in data
    assert "hotspots" in data
    assert len(data["hotspots"]) <= 10


# ============================================================================
# 3. AI Model Committee (Separate Mode)
# ============================================================================

def test_ai_model_committee_deliberation():
    """Validates multi-agent debate and anti-hallucination consensus."""
    orchestrator = ModelCommitteeOrchestrator()
    report = orchestrator.deliberate(
        bug_id="test-bug-committee",
        file_path="src/service/user.py",
        defect_description="Unvalidated user parameter used in sensitive calculation",
        patch_diff="--- a/src/service/user.py\n+++ b/src/service/user.py\n@@ -10,1 +10,3 @@\n+ if not isinstance(val, int) or val <= 0:\n+     raise ValueError('Invalid val')\n  return val * 10\n",
    )

    assert report.verdict.verdict in ("CONSENSUS_APPROVED", "MAJORITY_APPROVED_WITH_AMENDMENTS")
    assert report.verdict.consensus_score >= 80.0
    assert len(report.evaluations) == 3
    assert len(report.debate_transcript) >= 3


def test_ai_model_committee_endpoint(target_project_id: str):
    """Tests the REST endpoint POST /projects/{id}/committee/review."""
    resp = client.post(
        f"/api/v1/projects/{target_project_id}/committee/review",
        headers=AUTH,
        json={
            "bug_id": "test-comm-bug",
            "file_path": "src/auth.py",
            "defect_description": "SQL injection flaw",
            "patch_diff": "+ # parameterized query\n",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "verdict" in data
    assert "debate_transcript" in data
    assert len(data["members"]) == 3


# ============================================================================
# 4. Long-Term Learning from Repairs
# ============================================================================

def test_long_term_learning_memory_store(tmp_path: Path):
    """Validates learning new repair patterns and retrieving similar exemplars."""
    store = RepairMemoryStore(tmp_path / "test_memory.db")
    item = store.record_learned_repair(
        category="SECURITY",
        cwe="CWE-89",
        title="Custom SQL Parameterization Pattern",
        description="Replaces format string with dictionary params",
        diff_pattern="- raw_sql\n+ param_sql",
        fixed_code_snippet="execute(param_sql)",
        verification_pass_rate=100.0,
    )
    assert item.memory_id.startswith("mem-")

    # Retrieve similar
    similar = store.find_similar_repairs(cwe="CWE-89")
    assert len(similar) >= 1
    assert similar[0].cwe == "CWE-89"


def test_long_term_learning_endpoints(target_project_id: str):
    """Tests the REST endpoints for repair memory bank."""
    resp = client.get("/api/v1/observability/repair-memory", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "repairs" in data

    sim_resp = client.get(f"/api/v1/projects/{target_project_id}/bugs/test-bug-1/similar-repairs", headers=AUTH)
    assert sim_resp.status_code == 200
    assert isinstance(sim_resp.json(), list)


# ============================================================================
# 5. API Security Testing
# ============================================================================

def test_api_security_scanner_direct(tmp_path: Path):
    """Validates OWASP API Top 10 detection on REST routes."""
    api_file = tmp_path / "routes.py"
    api_file.write_text(
        "@app.delete('/users/{user_id}')\n"
        "def delete_user(user_id: str):\n"
        "    db.delete(user_id)\n"
        "    return {'ok': True}\n",
        encoding="utf-8"
    )

    scanner = ApiSecurityScanner(tmp_path)
    report = scanner.audit_project("test-api")
    assert report.total_endpoints_discovered >= 1
    assert report.vulnerable_endpoints_count >= 1
    assert any("Broken Authentication" in f.owasp_category for f in report.findings)


def test_api_security_endpoint(target_project_id: str):
    """Tests the REST endpoint GET /projects/{id}/api-security/audit."""
    resp = client.get(f"/api/v1/projects/{target_project_id}/api-security/audit", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "security_posture_grade" in data
    assert "owasp_coverage" in data


# ============================================================================
# 6. Bug Origin Detection
# ============================================================================

def test_bug_origin_tracker(tmp_path: Path):
    """Tests tracing defect introduction via Git archaeology."""
    tracker = BugOriginTracker(tmp_path)
    origin = tracker.trace_origin(
        bug_id="test-bug-org",
        file_path="src/main.py",
        line_number=10,
    )
    assert origin.bug_id == "test-bug-org"
    assert origin.origin_classification in ("UNCOMMITTED_LOCAL_CHANGE", "RECENT_REGRESSION", "LEGACY_CODEBASE")


def test_bug_origin_endpoint(target_project_id: str):
    """Tests the REST endpoint GET /projects/{id}/bugs/{bug_id}/origin."""
    resp = client.get(f"/api/v1/projects/{target_project_id}/bugs/test-b-1/origin", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "author_name" in data
    assert "commit_sha" in data
    assert "origin_classification" in data


# ============================================================================
# 7. Automatic Documentation
# ============================================================================

def test_auto_documentation_generator():
    """Validates ADR, Changelog, and Executive Brief generation."""
    gen = AutoDocumentationGenerator("Test Project")
    adr = gen.generate_adr(
        bug_id="bug-doc-1",
        defect_title="Authentication Bypass Invariant",
        cwe="CWE-287",
        file_path="src/auth.py",
        root_cause="Missing signature check",
        patch_strategy="Verify JWT HMAC before processing payload",
    )
    assert adr.status == "ACCEPTED"
    assert "## Decision" in adr.markdown_content

    cl = gen.generate_changelog(
        project_id="p-1",
        resolved_bugs=[{"bug_id": "b-1", "cwe": "CWE-287", "file": "src/auth.py", "description": "Auth check"}],
    )
    assert "Security Remediation Changelog" in cl.markdown_content


def test_auto_documentation_endpoints(target_project_id: str):
    """Tests the REST endpoints for ADR, Changelog, and Executive Brief."""
    r_adr = client.get(f"/api/v1/projects/{target_project_id}/documentation/adr", headers=AUTH)
    assert r_adr.status_code == 200
    assert "markdown_content" in r_adr.json()

    r_chg = client.get(f"/api/v1/projects/{target_project_id}/documentation/changelog", headers=AUTH)
    assert r_chg.status_code == 200
    assert "version" in r_chg.json()

    r_brf = client.get(f"/api/v1/projects/{target_project_id}/documentation/executive-brief", headers=AUTH)
    assert r_brf.status_code == 200
    assert "risk_score_reduction_pct" in r_brf.json()
