"""Unit tests for dependency call graph and import graph."""

from pathlib import Path
import pytest
from autopatch.intelligence.service import CodeIntelligenceService


def test_dependency_call_and_import_graphs(tmp_path: Path):
    """Verify call graph callers/callees and import graph traversal."""
    root = tmp_path / "graph_project"
    root.mkdir()

    # Module A: service.py
    code_a = """from utils import helper_func

def run_service():
    helper_func()
    compute_values()

def compute_values():
    return 42
"""
    (root / "service.py").write_text(code_a)

    # Module B: utils.py
    code_b = """def helper_func():
    return "done"
"""
    (root / "utils.py").write_text(code_b)

    service = CodeIntelligenceService()
    project_id = "proj_graph"
    graphs = service.index_project(project_id, root)

    # 1. Verify Import Graph
    imported = graphs.modules_imported_by("service.py")
    assert "utils" in imported

    importing = graphs.files_importing_module("utils")
    assert "service.py" in importing

    # 2. Verify Call Graph
    # run_service calls helper_func and compute_values
    callees_of_run = graphs.callees("service.py:run_service")
    assert any("helper_func" in c for c in callees_of_run)
    assert any("compute_values" in c for c in callees_of_run)

    # helper_func is called by run_service
    callers_of_helper = graphs.callers("helper_func")
    assert any("run_service" in c for c in callers_of_helper)
