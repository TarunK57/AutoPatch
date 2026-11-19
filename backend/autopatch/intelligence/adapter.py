"""Pluggable language adapter interface for tree-sitter AST parsing."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from autopatch.intelligence.models import FileASTIndex


class LanguageAdapter(ABC):
    """Abstract base class for all language-specific AST indexing adapters."""

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Name of the programming language (e.g. 'Python', 'JavaScript')."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """List of file extensions supported by this adapter (e.g. ['.py'])."""
        pass

    def can_handle(self, file_path: Path) -> bool:
        """Checks if this adapter handles the specified file path."""
        return file_path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def parse_file(self, rel_path: str, source_code: str) -> FileASTIndex:
        """Parses source code string into an AST index representation."""
        pass
