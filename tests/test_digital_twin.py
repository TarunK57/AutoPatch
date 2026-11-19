from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from autopatch.api.main import app
from autopatch.intelligence.digital_twin import CodebaseDigitalTwinBuilder


def test_digital_twin_builder_direct():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "tests").mkdir()

        (root / "src" / "auth.py").write_text("""
def verify_token(tok):
    if not tok:
        return False
    return True
""", encoding="utf-8")

        (root / "src" / "api.py").write_text("""
from src.auth import verify_token

class Router:
    @app.get
    def get_profile(token):
        if verify_token(token):
            return {"user": "alice"}
        return {"error": "unauthorized"}
""", encoding="utf-8")

        (root / "tests" / "test_auth.py").write_text("""
from src.auth import verify_token

def test_verify_token():
    assert verify_token("valid") is True
    assert verify_token("") is False
""", encoding="utf-8")

        builder = CodebaseDigitalTwinBuilder(root)
        model = builder.build_model()

        assert "nodes" in model
        assert "edges" in model
        assert "metrics" in model

        nodes = model["nodes"]
        assert len(nodes) >= 4
        node_types = {n["type"] for n in nodes}
        assert "module" in node_types
        assert "function" in node_types
        assert "test" in node_types

        # Test blast radius simulation
        impact = builder.analyze_patch_blast_radius(target_file="src/auth.py", function_hint="verify_token")
        assert "blast_radius" in impact
        blast = impact["blast_radius"]
        assert blast["total_affected"] >= 1
        assert "summary" in blast
        assert blast["overall_risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")


def test_digital_twin_endpoints():
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev_token_user_alice"}

    # 1. Create a project
    create_res = client.post(
        "/api/v1/projects",
        json={"name": "Twin-Test-Project"},
        headers=headers,
    )
    assert create_res.status_code == 201
    proj_id = create_res.json()["project_id"]

    # 2. Query digital twin
    twin_res = client.get(f"/api/v1/projects/{proj_id}/digital-twin", headers=headers)
    assert twin_res.status_code == 200
    data = twin_res.json()
    assert "nodes" in data
    assert "edges" in data
    assert "metrics" in data
    assert data["metrics"]["total_nodes"] > 0

    # 3. Query bug digital twin impact
    impact_res = client.get(
        f"/api/v1/projects/{proj_id}/bugs/test-bug-1/digital-twin-impact",
        headers=headers,
    )
    assert impact_res.status_code == 200
    imp_data = impact_res.json()
    assert imp_data["blast_radius"] is not None
    assert imp_data["blast_radius"]["total_affected"] >= 1
    assert imp_data["blast_radius"]["overall_risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
