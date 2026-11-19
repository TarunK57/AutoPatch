"""Unit tests and performance benchmarks for project mapping engine."""

import time
from pathlib import Path
from autopatch.ingestion.project_map import ProjectMapper


def test_project_map_50_file_repo_performance(tmp_path: Path):
    """Acceptance criterion: given a 50-file sample repo, API returns project map in under 5s."""
    repo_root = tmp_path / "sample_50_repo"
    repo_root.mkdir()

    # Generate 50 realistic files across multiple packages
    (repo_root / "requirements.txt").write_text("pytest>=7.0.0\nfastapi>=0.100.0\npydantic>=2.0\n")
    (repo_root / "main.py").write_text("from src.app import create_app\napp = create_app()\n")

    for i in range(1, 25):
        pkg = repo_root / f"src/pkg_{i}"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text(f"# Package {i}")
        (pkg / f"service_{i}.py").write_text(
            f"def do_task_{i}(x: int) -> int:\n    return x * {i}\n"
        )

    # Add test suite
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        (tests_dir / f"test_service_{i}.py").write_text(
            f"def test_task_{i}():\n    assert True\n"
        )

    mapper = ProjectMapper()

    start_time = time.perf_counter()
    project_map = mapper.build_project_map(repo_root)
    elapsed_time = time.perf_counter() - start_time

    # Acceptance criterion: must return in under 5 seconds
    assert elapsed_time < 5.0, f"Project map took {elapsed_time:.3f}s, expected < 5.0s"
    assert project_map.total_files >= 50, f"Expected at least 50 files, got {project_map.total_files}"
    assert "Python" in project_map.languages
    assert "main.py" in project_map.entry_points
    assert "requirements.txt" in project_map.dependency_manifests
    assert project_map.detected_test_framework == "pytest"
    assert project_map.test_command == "pytest"
    assert project_map.tree is not None


def test_test_framework_detection_js(tmp_path: Path):
    """Verify test framework and command detection for JS/TS projects."""
    js_repo = tmp_path / "js_repo"
    js_repo.mkdir()

    pkg_json = """{
        "name": "my-app",
        "scripts": {
            "test": "jest --coverage"
        },
        "devDependencies": {
            "jest": "^29.0.0"
        }
    }"""
    (js_repo / "package.json").write_text(pkg_json)
    (js_repo / "index.js").write_text("console.log('hi');")

    mapper = ProjectMapper()
    pmap = mapper.build_project_map(js_repo)

    assert "JavaScript" in pmap.languages
    assert pmap.detected_test_framework == "jest"
    assert pmap.test_command == "npm test"
    assert "index.js" in pmap.entry_points
