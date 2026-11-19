"""Code intelligence, AST indexing, search, and dependency graph modules."""

from autopatch.intelligence.models import (
    SourceRange,
    ClassDefinition,
    FunctionDefinition,
    MethodDefinition,
    ImportDefinition,
    FileASTIndex,
    SearchResult,
)
from autopatch.intelligence.adapter import LanguageAdapter
from autopatch.intelligence.python_adapter import PythonAdapter
from autopatch.intelligence.javascript_adapter import JavaScriptAdapter
from autopatch.intelligence.storage import CodeIndexRepository
from autopatch.intelligence.code_search import CodeSearchEngine
from autopatch.intelligence.graph import DependencyGraphs
from autopatch.intelligence.service import CodeIntelligenceService

__all__ = [
    "SourceRange",
    "ClassDefinition",
    "FunctionDefinition",
    "MethodDefinition",
    "ImportDefinition",
    "FileASTIndex",
    "SearchResult",
    "LanguageAdapter",
    "PythonAdapter",
    "JavaScriptAdapter",
    "CodeIndexRepository",
    "CodeSearchEngine",
    "DependencyGraphs",
    "CodeIntelligenceService",
]
