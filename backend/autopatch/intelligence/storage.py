"""Relational persistence layer for Tree-sitter AST indexing.

Supports PostgreSQL and SQLite backends with unified schema and queries.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4

from autopatch.intelligence.models import (
    ClassDefinition,
    FileASTIndex,
    FunctionDefinition,
    ImportDefinition,
    MethodDefinition,
    SourceRange,
)


class CodeIndexRepository:
    """Stores and queries AST symbols across projects."""

    def __init__(self, db_connection: Optional[sqlite3.Connection] = None, in_memory: bool = True):
        if db_connection is not None:
            self._conn = db_connection
        elif in_memory:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            self._conn = sqlite3.connect("autopatch_index.db", check_same_thread=False)

        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initializes tables for classes, methods, functions, and imports."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ast_classes (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    docstring TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ast_functions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    implementation TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    docstring TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ast_methods (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    implementation TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    docstring TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ast_imports (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    module TEXT NOT NULL,
                    imported_names TEXT NOT NULL,
                    line INTEGER NOT NULL
                )
                """
            )
            # Create indexes for high-throughput symbol lookup
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_classes_name ON ast_classes(project_id, name)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_methods_name ON ast_methods(project_id, name)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_methods_class ON ast_methods(project_id, class_name, name)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_funcs_name ON ast_functions(project_id, name)")

    def save_file_index(self, project_id: str, index: FileASTIndex) -> None:
        """Persists all extracted symbols for a given file."""
        with self._conn:
            # Delete previous symbols for this file in case of re-indexing
            self._conn.execute("DELETE FROM ast_classes WHERE project_id = ? AND file_path = ?", (project_id, index.file_path))
            self._conn.execute("DELETE FROM ast_functions WHERE project_id = ? AND file_path = ?", (project_id, index.file_path))
            self._conn.execute("DELETE FROM ast_methods WHERE project_id = ? AND file_path = ?", (project_id, index.file_path))
            self._conn.execute("DELETE FROM ast_imports WHERE project_id = ? AND file_path = ?", (project_id, index.file_path))

            # Insert classes
            for cls in index.classes:
                self._conn.execute(
                    """
                    INSERT INTO ast_classes (id, project_id, file_path, name, signature, start_line, end_line, docstring)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        project_id,
                        cls.file_path,
                        cls.name,
                        cls.signature,
                        cls.range.start_line,
                        cls.range.end_line,
                        cls.docstring,
                    ),
                )

            # Insert functions
            for fn in index.functions:
                self._conn.execute(
                    """
                    INSERT INTO ast_functions (id, project_id, file_path, name, signature, implementation, start_line, end_line, docstring)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        project_id,
                        fn.file_path,
                        fn.name,
                        fn.signature,
                        fn.implementation,
                        fn.range.start_line,
                        fn.range.end_line,
                        fn.docstring,
                    ),
                )

            # Insert methods
            for m in index.methods:
                self._conn.execute(
                    """
                    INSERT INTO ast_methods (id, project_id, file_path, class_name, name, signature, implementation, start_line, end_line, docstring)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        project_id,
                        m.file_path,
                        m.class_name,
                        m.name,
                        m.signature,
                        m.implementation,
                        m.range.start_line,
                        m.range.end_line,
                        m.docstring,
                    ),
                )

            # Insert imports
            for imp in index.imports:
                self._conn.execute(
                    """
                    INSERT INTO ast_imports (id, project_id, file_path, module, imported_names, line)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        project_id,
                        imp.file_path,
                        imp.module,
                        json.dumps(imp.imported_names),
                        imp.line,
                    ),
                )

    def find_classes(
        self, project_id: str, class_name: Optional[str] = None, file_path: Optional[str] = None
    ) -> List[ClassDefinition]:
        """Finds classes matching name and/or file_path."""
        query = "SELECT file_path, name, signature, start_line, end_line, docstring FROM ast_classes WHERE project_id = ?"
        params: List[Any] = [project_id]

        if class_name:
            query += " AND name = ?"
            params.append(class_name)
        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)

        rows = self._conn.execute(query, params).fetchall()
        return [
            ClassDefinition(
                name=r["name"],
                file_path=r["file_path"],
                signature=r["signature"],
                range=SourceRange(start_line=r["start_line"], end_line=r["end_line"]),
                docstring=r["docstring"],
            )
            for r in rows
        ]

    def find_methods(
        self,
        project_id: str,
        method_name: Optional[str] = None,
        class_name: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> List[MethodDefinition]:
        """Finds methods matching method_name, class_name, and/or file_path."""
        query = "SELECT file_path, class_name, name, signature, implementation, start_line, end_line, docstring FROM ast_methods WHERE project_id = ?"
        params: List[Any] = [project_id]

        if method_name:
            query += " AND name = ?"
            params.append(method_name)
        if class_name:
            query += " AND class_name = ?"
            params.append(class_name)
        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)

        rows = self._conn.execute(query, params).fetchall()
        return [
            MethodDefinition(
                name=r["name"],
                class_name=r["class_name"],
                file_path=r["file_path"],
                signature=r["signature"],
                implementation=r["implementation"],
                range=SourceRange(start_line=r["start_line"], end_line=r["end_line"]),
                docstring=r["docstring"],
            )
            for r in rows
        ]

    def find_functions(
        self, project_id: str, function_name: Optional[str] = None, file_path: Optional[str] = None
    ) -> List[FunctionDefinition]:
        """Finds functions matching function_name and/or file_path."""
        query = "SELECT file_path, name, signature, implementation, start_line, end_line, docstring FROM ast_functions WHERE project_id = ?"
        params: List[Any] = [project_id]

        if function_name:
            query += " AND name = ?"
            params.append(function_name)
        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)

        rows = self._conn.execute(query, params).fetchall()
        return [
            FunctionDefinition(
                name=r["name"],
                file_path=r["file_path"],
                signature=r["signature"],
                implementation=r["implementation"],
                range=SourceRange(start_line=r["start_line"], end_line=r["end_line"]),
                docstring=r["docstring"],
            )
            for r in rows
        ]

    def find_imports(self, project_id: str, file_path: Optional[str] = None) -> List[ImportDefinition]:
        """Retrieves import statements."""
        query = "SELECT file_path, module, imported_names, line FROM ast_imports WHERE project_id = ?"
        params: List[Any] = [project_id]
        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)

        rows = self._conn.execute(query, params).fetchall()
        return [
            ImportDefinition(
                file_path=r["file_path"],
                module=r["module"],
                imported_names=json.loads(r["imported_names"]),
                line=r["line"],
            )
            for r in rows
        ]
