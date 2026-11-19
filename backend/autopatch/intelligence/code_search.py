"""AutoCodeRover-compatible Code Search API.

Implements the precise 7 search operations:
1. search_class(cls) - returns signature only
2. search_class_in_file(cls, f) - returns signature only
3. search_method(m) - returns implementation
4. search_method_in_class(m, cls) - returns implementation
5. search_method_in_file(m, f) - returns implementation
6. search_code(snippet) - returns matching line +/- 3 context lines
7. search_code_in_file(snippet, f) - returns matching line +/- 3 context lines
"""

from pathlib import Path
from typing import List, Optional
from autopatch.intelligence.models import SearchResult
from autopatch.intelligence.storage import CodeIndexRepository


class CodeSearchEngine:
    """Provides high-precision symbol and snippet retrieval modeled after AutoCodeRover."""

    def __init__(self, project_root: Path, project_id: str, repository: CodeIndexRepository):
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.repository = repository

    def search_class(self, class_name: str) -> List[SearchResult]:
        """Searches for a class by name across the project.

        Returns signature only to keep LLM context concise.
        """
        classes = self.repository.find_classes(self.project_id, class_name=class_name)
        return [
            SearchResult(
                file_path=c.file_path,
                symbol_name=c.name,
                symbol_type="class",
                content=c.signature,
                line_start=c.range.start_line,
                line_end=c.range.end_line,
            )
            for c in classes
        ]

    def search_class_in_file(self, class_name: str, file_path: str) -> Optional[SearchResult]:
        """Searches for a class by name within a specific file.

        Returns signature only, or None if not found.
        """
        classes = self.repository.find_classes(self.project_id, class_name=class_name, file_path=file_path)
        if not classes:
            return None
        c = classes[0]
        return SearchResult(
            file_path=c.file_path,
            symbol_name=c.name,
            symbol_type="class",
            content=c.signature,
            line_start=c.range.start_line,
            line_end=c.range.end_line,
        )

    def search_method(self, method_name: str) -> List[SearchResult]:
        """Searches for a method by name across all classes in the project.

        Returns full method implementation.
        """
        methods = self.repository.find_methods(self.project_id, method_name=method_name)
        return [
            SearchResult(
                file_path=m.file_path,
                symbol_name=f"{m.class_name}.{m.name}",
                symbol_type="method",
                content=m.implementation,
                line_start=m.range.start_line,
                line_end=m.range.end_line,
            )
            for m in methods
        ]

    def search_method_in_class(self, method_name: str, class_name: str) -> List[SearchResult]:
        """Searches for a method inside a specific class.

        Returns full method implementation.
        """
        methods = self.repository.find_methods(
            self.project_id, method_name=method_name, class_name=class_name
        )
        return [
            SearchResult(
                file_path=m.file_path,
                symbol_name=f"{m.class_name}.{m.name}",
                symbol_type="method",
                content=m.implementation,
                line_start=m.range.start_line,
                line_end=m.range.end_line,
            )
            for m in methods
        ]

    def search_method_in_file(self, method_name: str, file_path: str) -> List[SearchResult]:
        """Searches for a method within a specific file.

        Returns full method implementation.
        """
        methods = self.repository.find_methods(
            self.project_id, method_name=method_name, file_path=file_path
        )
        return [
            SearchResult(
                file_path=m.file_path,
                symbol_name=f"{m.class_name}.{m.name}",
                symbol_type="method",
                content=m.implementation,
                line_start=m.range.start_line,
                line_end=m.range.end_line,
            )
            for m in methods
        ]

    def search_code(self, snippet: str) -> List[SearchResult]:
        """Searches for code snippet across all indexed project files.

        Returns matching line +/- 3 lines of surrounding context.
        """
        results: List[SearchResult] = []
        if not snippet.strip():
            return results

        # Walk through files in project root
        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue
            # Skip hidden/ignored files
            if any(part.startswith(".") or part in {"node_modules", "venv", "__pycache__"} for part in path.parts):
                continue

            rel_path = str(path.relative_to(self.project_root))
            file_results = self.search_code_in_file(snippet, rel_path)
            results.extend(file_results)

        return results

    def search_code_in_file(self, snippet: str, file_path: str) -> List[SearchResult]:
        """Searches for code snippet within a specific file.

        Returns matching line +/- 3 lines of surrounding context.
        """
        results: List[SearchResult] = []
        if not snippet.strip():
            return results

        full_path = (self.project_root / file_path).resolve()
        if not full_path.is_file():
            return results

        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return results

        total_lines = len(lines)
        for i, line in enumerate(lines):
            if snippet in line:
                start_idx = max(0, i - 3)
                end_idx = min(total_lines, i + 4)
                context_lines = lines[start_idx:end_idx]
                content = "\n".join(context_lines)

                results.append(
                    SearchResult(
                        file_path=file_path,
                        symbol_name=f"line_{i + 1}",
                        symbol_type="code",
                        content=content,
                        line_start=start_idx + 1,
                        line_end=end_idx,
                    )
                )

        return results
