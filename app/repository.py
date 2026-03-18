"""SQLite repository primitives for the application."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteRepository:
    """Repository for SQLite schema initialization and connectivity checks."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._connection = self._connect()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            db_file = Path(self.db_path)
            try:
                db_file.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                fallback_dir = Path.cwd() / "data"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                db_file = fallback_dir / db_file.name
                self.db_path = str(db_file)
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER,
                origin TEXT NOT NULL CHECK (origin IN ('odoo', 'local')),
                title TEXT NOT NULL,
                description TEXT,
                project_id INTEGER,
                deadline TEXT,
                state TEXT,
                assigned_date TEXT,
                completed_date TEXT,
                pending_priority INTEGER,
                confirmed_priority INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER,
                title TEXT NOT NULL,
                branch_name TEXT,
                repo_url TEXT,
                state TEXT,
                review_result TEXT,
                review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'complete', 'failed')),
                reviewed_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sync_log (
                model TEXT PRIMARY KEY,
                last_synced_at TEXT,
                record_count INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS push_queue (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'duplicate_check', 'pushed', 'failed')),
                duplicate_candidate_odoo_id INTEGER,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL UNIQUE,
                summary_text TEXT,
                review_section_text TEXT,
                status TEXT NOT NULL CHECK (status IN ('partial', 'complete')),
                priority_approved INTEGER NOT NULL DEFAULT 0
            )
            """,
        ]
        with self._connection:
            for statement in statements:
                self._connection.execute(statement)

    def is_reachable(self) -> bool:
        self._connection.execute("SELECT 1")
        return True

    def close(self) -> None:
        self._connection.close()
