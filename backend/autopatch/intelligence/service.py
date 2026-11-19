"""Unified Code Intelligence Service orchestrating AST parsing, indexing, and search."""

from pathlib import Path
from typing import Dict, List, Optional
from autopatch.core.logging import get_logger
from autopatch.ingestion.extractor import DEFAULT_IGNORE_DIRS, DEFAULT_IGNORE_FILES
from autopatch.intelligence.adapter import LanguageAdapter
from autopatch.intelligence.code_search import CodeSearchEngine
from autopatch.intelligence.graph import DependencyGraphs
from autopatch.intelligence.javascript_adapter import JavaScriptAdapter
from autopatch.intelligence.models import FileASTIndex
from autopatch.intelligence.python_adapter import PythonAdapter
from autopatch.intelligence.storage import CodeIndexRepository

logger = get_logger(__name__)


class CodeIntelligenceService:
    """Orchestrates multi-language AST extraction, graph building, and code search."""

    def __init__(
        self,
        repository: Optional[CodeIndexRepository] = None,
        adapters: Optional[List[LanguageAdapter]] = None,
    ):
        self.repository = repository or CodeIndexRepository(in_memory=True)
        self.adapters = adapters or [PythonAdapter(), JavaScriptAdapter()]
        self.graphs_by_project: Dict[str, DependencyGraphs] = {}

    def get_adapter_for_path(self, path: Path) -> Optional[LanguageAdapter]:
        for adapter in self.adapters:
            if adapter.can_handle(path):
                return adapter
        return None

    def index_project(self, project_id: str, project_root: Path) -> DependencyGraphs:
        """Indexes all supported source files in a project workspace."""
        root = project_root.resolve()
        indices: List[FileASTIndex] = []

        for p in root.rglob("*"):
            if not p.is_file():
                continue
            # Apply ignore filters
            if any(part in DEFAULT_IGNORE_DIRS for part in p.parts) or p.name in DEFAULT_IGNORE_FILES:
                continue

            adapter = self.get_adapter_for_path(p)
            if not adapter:
                continue

            rel_path = str(p.relative_to(root))
            try:
                code = p.read_text(encoding="utf-8", errors="replace")
                file_index = adapter.parse_file(rel_path, code)
                self.repository.save_file_index(project_id, file_index)
                indices.append(file_index)
            except Exception as e:
                logger.warning(
                    f"Failed to parse file {rel_path} with {adapter.language_name}",
                    extra={"data": {"error": str(e)}},
                )

        # Build graphs
        dep_graphs = DependencyGraphs()
        dep_graphs.build_from_indices(indices)
        self.graphs_by_project[project_id] = dep_graphs

        logger.info(
            f"Successfully indexed project {project_id}",
            extra={"data": {"files_indexed": len(indices)}},
        )
        return dep_graphs

    def get_search_engine(self, project_id: str, project_root: Path) -> CodeSearchEngine:
        """Returns a configured CodeSearchEngine for the specified project."""
        return CodeSearchEngine(
            project_root=project_root,
            project_id=project_id,
            repository=self.repository,
        )

    def get_graphs(self, project_id: str) -> Optional[DependencyGraphs]:
        """Returns dependency graphs for the specified project."""
        return self.graphs_by_project.get(project_id)
