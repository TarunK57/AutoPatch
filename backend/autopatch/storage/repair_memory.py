"""Long-term Learning Memory Bank storing and retrieving verified code repair patterns."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from autopatch.core.logging import get_logger
from autopatch.storage.db import get_default_db_path

logger = get_logger(__name__)


class LearnedRepairItem(BaseModel):
    memory_id: str
    project_id: Optional[str] = None
    bug_id: Optional[str] = None
    category: str
    cwe: Optional[str] = None
    title: str
    description: str
    diff_pattern: str
    fixed_code_snippet: str
    language: str = "python"
    verification_pass_rate: float = 100.0
    times_applied: int = 1
    confidence_score: float = 0.95
    learned_at: str


class RepairMemoryStats(BaseModel):
    total_learned_patterns: int
    total_times_reused: int
    top_cwe_covered: List[Dict[str, Any]]
    average_confidence: float


class RepairMemoryStore:
    """Persistent SQLite repository for cross-session repair transfer learning."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or get_default_db_path().parent / "repair_memory.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_exemplars_if_empty()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS repair_memory (
                    memory_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    bug_id TEXT,
                    category TEXT NOT NULL,
                    cwe TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    diff_pattern TEXT NOT NULL,
                    fixed_code_snippet TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'python',
                    verification_pass_rate REAL NOT NULL DEFAULT 100.0,
                    times_applied INTEGER NOT NULL DEFAULT 1,
                    confidence_score REAL NOT NULL DEFAULT 0.95,
                    learned_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_repair_cwe ON repair_memory (cwe);
                CREATE INDEX IF NOT EXISTS idx_repair_cat ON repair_memory (category);
                """
            )
            conn.commit()

    def record_learned_repair(
        self,
        category: str,
        diff_pattern: str,
        fixed_code_snippet: str,
        title: str,
        description: str,
        cwe: Optional[str] = None,
        project_id: Optional[str] = None,
        bug_id: Optional[str] = None,
        language: str = "python",
        verification_pass_rate: float = 100.0,
        confidence_score: float = 0.95,
    ) -> LearnedRepairItem:
        """Records a new verified repair into persistent memory or increments reuse counter."""
        memory_id = f"mem-{uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Check if identical diff pattern already exists
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_id, times_applied FROM repair_memory WHERE diff_pattern = ?",
                (diff_pattern.strip(),),
            )
            existing = cursor.fetchone()
            if existing:
                existing_id = existing["memory_id"]
                new_times = existing["times_applied"] + 1
                conn.execute(
                    "UPDATE repair_memory SET times_applied = ?, confidence_score = MIN(1.0, confidence_score + 0.02) WHERE memory_id = ?",
                    (new_times, existing_id),
                )
                conn.commit()
                return self.get_repair(existing_id)  # type: ignore

            conn.execute(
                """
                INSERT INTO repair_memory (
                    memory_id, project_id, bug_id, category, cwe, title, description,
                    diff_pattern, fixed_code_snippet, language, verification_pass_rate,
                    times_applied, confidence_score, learned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    project_id,
                    bug_id,
                    category.upper(),
                    cwe,
                    title,
                    description,
                    diff_pattern.strip(),
                    fixed_code_snippet.strip(),
                    language.lower(),
                    float(verification_pass_rate),
                    1,
                    float(confidence_score),
                    now_iso,
                ),
            )
            conn.commit()

        logger.info(f"Learned new repair pattern {memory_id} for {cwe or category}")
        return LearnedRepairItem(
            memory_id=memory_id,
            project_id=project_id,
            bug_id=bug_id,
            category=category.upper(),
            cwe=cwe,
            title=title,
            description=description,
            diff_pattern=diff_pattern.strip(),
            fixed_code_snippet=fixed_code_snippet.strip(),
            language=language.lower(),
            verification_pass_rate=verification_pass_rate,
            times_applied=1,
            confidence_score=confidence_score,
            learned_at=now_iso,
        )

    def find_similar_repairs(
        self,
        category: Optional[str] = None,
        cwe: Optional[str] = None,
        language: str = "python",
        limit: int = 5,
    ) -> List[LearnedRepairItem]:
        """Retrieves top matching learned repair patterns for few-shot transfer guidance."""
        query = "SELECT * FROM repair_memory WHERE 1=1"
        params: List[Any] = []

        if cwe:
            query += " AND cwe = ?"
            params.append(cwe)
        elif category:
            query += " AND category = ?"
            params.append(category.upper())

        query += " ORDER BY times_applied DESC, confidence_score DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        if not rows and cwe:
            # Fallback to category search if specific CWE has no hits
            return self.find_similar_repairs(category=category, cwe=None, language=language, limit=limit)

        results: List[LearnedRepairItem] = []
        for r in rows:
            results.append(
                LearnedRepairItem(
                    memory_id=r["memory_id"],
                    project_id=r["project_id"],
                    bug_id=r["bug_id"],
                    category=r["category"],
                    cwe=r["cwe"],
                    title=r["title"],
                    description=r["description"],
                    diff_pattern=r["diff_pattern"],
                    fixed_code_snippet=r["fixed_code_snippet"],
                    language=r["language"],
                    verification_pass_rate=r["verification_pass_rate"],
                    times_applied=r["times_applied"],
                    confidence_score=r["confidence_score"],
                    learned_at=r["learned_at"],
                )
            )
        return results

    def list_all_repairs(self, limit: int = 50) -> List[LearnedRepairItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repair_memory ORDER BY times_applied DESC, learned_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()

        return [
            LearnedRepairItem(
                memory_id=r["memory_id"],
                project_id=r["project_id"],
                bug_id=r["bug_id"],
                category=r["category"],
                cwe=r["cwe"],
                title=r["title"],
                description=r["description"],
                diff_pattern=r["diff_pattern"],
                fixed_code_snippet=r["fixed_code_snippet"],
                language=r["language"],
                verification_pass_rate=r["verification_pass_rate"],
                times_applied=r["times_applied"],
                confidence_score=r["confidence_score"],
                learned_at=r["learned_at"],
            )
            for r in rows
        ]

    def get_repair(self, memory_id: str) -> Optional[LearnedRepairItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repair_memory WHERE memory_id = ?", (memory_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return LearnedRepairItem(
                memory_id=r["memory_id"],
                project_id=r["project_id"],
                bug_id=r["bug_id"],
                category=r["category"],
                cwe=r["cwe"],
                title=r["title"],
                description=r["description"],
                diff_pattern=r["diff_pattern"],
                fixed_code_snippet=r["fixed_code_snippet"],
                language=r["language"],
                verification_pass_rate=r["verification_pass_rate"],
                times_applied=r["times_applied"],
                confidence_score=r["confidence_score"],
                learned_at=r["learned_at"],
            )

    def get_stats(self) -> RepairMemoryStats:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(times_applied), 0), COALESCE(AVG(confidence_score), 0.95) FROM repair_memory")
            row = cursor.fetchone()
            tot_patterns = row[0]
            tot_reused = row[1]
            avg_conf = round(row[2], 2)

            cursor.execute("SELECT cwe, COUNT(*) as cnt FROM repair_memory WHERE cwe IS NOT NULL GROUP BY cwe ORDER BY cnt DESC LIMIT 5")
            top_cwes = [{"cwe": r["cwe"], "count": r["cnt"]} for r in cursor.fetchall()]

        return RepairMemoryStats(
            total_learned_patterns=tot_patterns,
            total_times_reused=tot_reused,
            top_cwe_covered=top_cwes,
            average_confidence=avg_conf,
        )

    def _seed_exemplars_if_empty(self) -> None:
        """Seeds proven baseline repair templates for zero-day transfer guidance."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM repair_memory")
            if cursor.fetchone()[0] > 0:
                return

        seeds = [
            {
                "cwe": "CWE-89",
                "category": "SECURITY",
                "title": "SQL Injection Parameterized Binding",
                "description": "Replaces string interpolation/formatting in SQL queries with safe parameterized bind parameters.",
                "diff_pattern": "- cursor.execute(f\"SELECT * FROM users WHERE id = '{user_id}'\")\n+ cursor.execute(\"SELECT * FROM users WHERE id = :user_id\", {\"user_id\": user_id})",
                "fixed_code_snippet": "cursor.execute(\"SELECT * FROM users WHERE id = :user_id\", {\"user_id\": user_id})",
                "times_applied": 14,
            },
            {
                "cwe": "CWE-22",
                "category": "SECURITY",
                "title": "Path Traversal Safe Resolution Guard",
                "description": "Enforces os.path.realpath / Path.resolve() check ensuring target path stays strictly inside base directory.",
                "diff_pattern": "- file_path = os.path.join(base_dir, user_filename)\n+ safe_path = (Path(base_dir) / user_filename).resolve()\n+ if not safe_path.is_relative_to(Path(base_dir).resolve()):\n+     raise ValueError('Path traversal attempt detected')",
                "fixed_code_snippet": "safe_path = (Path(base_dir) / user_filename).resolve()\nif not safe_path.is_relative_to(Path(base_dir).resolve()):\n    raise ValueError('Path traversal attempt detected')",
                "times_applied": 9,
            },
            {
                "cwe": "CWE-20",
                "category": "INPUT_VALIDATION",
                "title": "Strict Type & Value Bounds Assertion",
                "description": "Validates boundary ranges and non-empty string constraints before proceeding with business logic.",
                "diff_pattern": "+ if not isinstance(quantity, int) or quantity <= 0:\n+     raise ValueError('Quantity must be a positive integer')\n  return calculate_total(quantity, price)",
                "fixed_code_snippet": "if not isinstance(quantity, int) or quantity <= 0:\n    raise ValueError('Quantity must be a positive integer')",
                "times_applied": 12,
            },
            {
                "cwe": "CWE-476",
                "category": "LOGIC_ERROR",
                "title": "Defensive NoneType Safe Navigation Guard",
                "description": "Adds defensive early return or fallback default when dictionary key lookup or nullable query returns None.",
                "diff_pattern": "- user_role = user_record['role']\n+ if user_record is None:\n+     return None\n+ user_role = user_record.get('role', 'guest')",
                "fixed_code_snippet": "if user_record is None:\n    return None\nuser_role = user_record.get('role', 'guest')",
                "times_applied": 19,
            },
            {
                "cwe": "CWE-775",
                "category": "RESOURCE_LEAK",
                "title": "Context Manager Resource Handle Invariant",
                "description": "Wraps manual file or connection handle in deterministic with-statement RAII block.",
                "diff_pattern": "- f = open(filename, 'r')\n- data = f.read()\n- f.close()\n+ with open(filename, 'r', encoding='utf-8') as f:\n+     data = f.read()",
                "fixed_code_snippet": "with open(filename, 'r', encoding='utf-8') as f:\n    data = f.read()",
                "times_applied": 8,
            },
        ]

        for s in seeds:
            self.record_learned_repair(
                category=s["category"],
                cwe=s["cwe"],
                title=s["title"],
                description=s["description"],
                diff_pattern=s["diff_pattern"],
                fixed_code_snippet=s["fixed_code_snippet"],
                verification_pass_rate=100.0,
                confidence_score=0.98,
            )
            # update times_applied to seed value
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE repair_memory SET times_applied = ? WHERE cwe = ?",
                    (s["times_applied"], s["cwe"]),
                )
                conn.commit()


# Global singleton instance
global_repair_memory = RepairMemoryStore()
