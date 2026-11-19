"""Project mapping engine for AutoPatch.

Builds comprehensive project topology:
- Directory and file tree
- Entry point detection (Python & JS/TS)
- Dependency manifests
- Detected test framework and exact command to run tests
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from autopatch.ingestion.extractor import DEFAULT_IGNORE_DIRS, DEFAULT_IGNORE_FILES


class TreeNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: int = 0
    children: Optional[List["TreeNode"]] = None


class ProjectMap(BaseModel):
    root_path: str
    total_files: int
    total_dirs: int
    languages: List[str]
    tree: TreeNode
    entry_points: List[str]
    dependency_manifests: List[str]
    detected_test_framework: Optional[str]
    test_command: Optional[str]


# Common candidate names for application entry points
ENTRY_POINT_CANDIDATES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "cli.py",
    "run.py",
    "index.ts",
    "index.js",
    "server.ts",
    "server.js",
    "main.ts",
    "main.js",
    "app.ts",
    "app.js",
}

DEPENDENCY_MANIFESTS = {
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}


class ProjectMapper:
    """Analyzes workspace layout, dependencies, entry points, and test framework configuration."""

    def __init__(
        self,
        ignore_dirs: Optional[Set[str]] = None,
        ignore_files: Optional[Set[str]] = None,
    ):
        self.ignore_dirs = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
        self.ignore_files = ignore_files if ignore_files is not None else DEFAULT_IGNORE_FILES

    def build_project_map(self, root_dir: Path) -> ProjectMap:
        """Constructs the complete ProjectMap for the provided directory."""
        root = root_dir.resolve()
        if not root.is_dir():
            raise ValueError(f"Target path {root} is not a valid directory.")

        total_files = 0
        total_dirs = 0
        detected_languages: Set[str] = set()
        entry_points: List[str] = []
        manifests: List[str] = []

        def walk_tree(current_dir: Path) -> TreeNode:
            nonlocal total_files, total_dirs
            rel_dir = str(current_dir.relative_to(root))
            if rel_dir == ".":
                rel_dir = ""

            children: List[TreeNode] = []
            try:
                entries = sorted(current_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return TreeNode(name=current_dir.name, path=rel_dir, is_dir=True, children=[])

            for entry in entries:
                if entry.name in self.ignore_dirs or entry.name in self.ignore_files:
                    continue

                rel_path = str(entry.relative_to(root))

                if entry.is_dir():
                    total_dirs += 1
                    child_node = walk_tree(entry)
                    children.append(child_node)
                elif entry.is_file():
                    total_files += 1
                    size = entry.stat().st_size
                    children.append(
                        TreeNode(name=entry.name, path=rel_path, is_dir=False, size_bytes=size)
                    )

                    # Language detection from extensions
                    ext = entry.suffix.lower()
                    if ext == ".py":
                        detected_languages.add("Python")
                    elif ext in {".js", ".jsx", ".mjs"}:
                        detected_languages.add("JavaScript")
                    elif ext in {".ts", ".tsx"}:
                        detected_languages.add("TypeScript")

                    # Check for manifest
                    if entry.name in DEPENDENCY_MANIFESTS:
                        manifests.append(rel_path)

                    # Check for standard entry point candidate
                    if entry.name.lower() in ENTRY_POINT_CANDIDATES:
                        entry_points.append(rel_path)

            return TreeNode(
                name=current_dir.name or str(root),
                path=rel_dir,
                is_dir=True,
                children=children,
            )

        root_tree = walk_tree(root)

        # Inspect package.json for additional entry points
        package_json_path = root / "package.json"
        if package_json_path.is_file():
            try:
                with open(package_json_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    if "main" in pkg_data and isinstance(pkg_data["main"], str):
                        main_entry = pkg_data["main"].lstrip("./")
                        if main_entry not in entry_points:
                            entry_points.append(main_entry)
            except Exception:
                pass

        test_framework, test_cmd = self._detect_test_framework(root, detected_languages)

        return ProjectMap(
            root_path=str(root),
            total_files=total_files,
            total_dirs=total_dirs,
            languages=sorted(list(detected_languages)),
            tree=root_tree,
            entry_points=sorted(entry_points),
            dependency_manifests=sorted(manifests),
            detected_test_framework=test_framework,
            test_command=test_cmd,
        )

    def _detect_test_framework(self, root: Path, languages: Set[str]) -> tuple[Optional[str], Optional[str]]:
        """Determines the test framework and the exact command to execute."""
        # 1. Check Python frameworks
        if "Python" in languages:
            # Check for pytest configs or requirements
            pytest_indicators = [
                root / "pytest.ini",
                root / "setup.cfg",
                root / "pyproject.toml",
            ]
            has_pytest = False
            for ind in pytest_indicators:
                if ind.is_file():
                    try:
                        content = ind.read_text(encoding="utf-8", errors="ignore")
                        if "pytest" in content or "[tool.pytest" in content:
                            has_pytest = True
                            break
                    except Exception:
                        pass

            req_file = root / "requirements.txt"
            if req_file.is_file():
                try:
                    if "pytest" in req_file.read_text(encoding="utf-8", errors="ignore"):
                        has_pytest = True
                except Exception:
                    pass

            # Check if any test files exist
            test_files = list(root.glob("**/test_*.py")) + list(root.glob("**/*_test.py"))
            if has_pytest or test_files:
                return "pytest", "pytest"
            return "unittest", "python -m unittest discover"

        # 2. Check JS/TS frameworks
        if "JavaScript" in languages or "TypeScript" in languages:
            pkg_json = root / "package.json"
            if pkg_json.is_file():
                try:
                    with open(pkg_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    scripts = data.get("scripts", {})
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                    if "test" in scripts:
                        # package.json defines a test script
                        test_script = scripts["test"]
                        if "jest" in test_script or "jest" in deps:
                            return "jest", "npm test"
                        if "vitest" in test_script or "vitest" in deps:
                            return "vitest", "npm test"
                        if "mocha" in test_script or "mocha" in deps:
                            return "mocha", "npm test"
                        return "npm-test", "npm test"

                    if "vitest" in deps:
                        return "vitest", "npx vitest run"
                    if "jest" in deps:
                        return "jest", "npx jest"
                except Exception:
                    pass
            return "jest", "npm test"

        return None, None
