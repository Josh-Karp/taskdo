"""SQLite repository primitives for the application."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
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
                odoo_id INTEGER UNIQUE,
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
                odoo_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER UNIQUE,
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

    def upsert_projects(self, records: list[dict]) -> None:
        with self._connection:
            for record in records:
                existing = self._connection.execute(
                    "SELECT id FROM projects WHERE odoo_id = ?",
                    (record["id"],),
                ).fetchone()
                if existing is None:
                    self._connection.execute(
                        """
                        INSERT INTO projects (odoo_id, name, active)
                        VALUES (?, ?, ?)
                        """,
                        (
                            record["id"],
                            record.get("name", ""),
                            1 if record.get("active", True) else 0,
                        ),
                    )
                else:
                    self._connection.execute(
                        """
                        UPDATE projects
                        SET name = ?, active = ?
                        WHERE id = ?
                        """,
                        (
                            record.get("name", ""),
                            1 if record.get("active", True) else 0,
                            existing[0],
                        ),
                    )

    def upsert_tasks(self, records: list[dict]) -> None:
        with self._connection:
            for record in records:
                project_id = record.get("project_id")
                if isinstance(project_id, list) and project_id:
                    project_id = project_id[0]
                stage = record.get("stage_id")
                if isinstance(stage, list) and len(stage) > 1:
                    state = str(stage[1])
                else:
                    state = str(stage) if stage else "open"
                existing = self._connection.execute(
                    "SELECT id FROM tasks WHERE odoo_id = ?",
                    (record["id"],),
                ).fetchone()
                if existing is None:
                    self._connection.execute(
                        """
                        INSERT INTO tasks (
                            odoo_id,
                            origin,
                            title,
                            description,
                            project_id,
                            deadline,
                            state,
                            assigned_date,
                            completed_date,
                            pending_priority,
                            confirmed_priority
                        )
                        VALUES (?, 'odoo', ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                        """,
                        (
                            record["id"],
                            record.get("name", ""),
                            record.get("description"),
                            project_id,
                            record.get("date_deadline"),
                            state,
                            record.get("date_assign"),
                        ),
                    )
                else:
                    self._connection.execute(
                        """
                        UPDATE tasks
                        SET origin = 'odoo',
                            title = ?,
                            description = ?,
                            project_id = ?,
                            deadline = ?,
                            state = ?,
                            assigned_date = ?
                        WHERE id = ?
                        """,
                        (
                            record.get("name", ""),
                            record.get("description"),
                            project_id,
                            record.get("date_deadline"),
                            state,
                            record.get("date_assign"),
                            existing[0],
                        ),
                    )

    def mark_tasks_cancelled(self, odoo_ids_not_in: list[int]) -> None:
        with self._connection:
            if not odoo_ids_not_in:
                self._connection.execute(
                    "UPDATE tasks SET state = 'cancelled' WHERE origin = 'odoo'"
                )
                return
            placeholders = ",".join("?" for _ in odoo_ids_not_in)
            query = (
                "UPDATE tasks "
                "SET state = 'cancelled' "
                "WHERE origin = 'odoo' AND odoo_id NOT IN (" + placeholders + ")"
            )
            self._connection.execute(query, tuple(odoo_ids_not_in))

    def upsert_reviews(self, records: list[dict]) -> None:
        with self._connection:
            for record in records:
                existing = self._connection.execute(
                    "SELECT review_result, review_status FROM reviews WHERE odoo_id = ?",
                    (record["id"],),
                ).fetchone()
                if existing is None:
                    self._connection.execute(
                        """
                        INSERT INTO reviews (
                            odoo_id,
                            title,
                            branch_name,
                            repo_url,
                            state,
                            review_result,
                            review_status,
                            reviewed_at
                        )
                        VALUES (?, ?, ?, ?, ?, NULL, 'pending', NULL)
                        """,
                        (
                            record["id"],
                            record.get("title", f"Review {record['id']}"),
                            record.get("branch_name"),
                            record.get("repo_url"),
                            record.get("state", "pending"),
                        ),
                    )
                    continue

                review_result, review_status = existing
                if review_result is not None:
                    status_to_write = review_status
                else:
                    status_to_write = "pending"
                self._connection.execute(
                    """
                    UPDATE reviews
                    SET title = ?,
                        branch_name = ?,
                        repo_url = ?,
                        state = ?,
                        review_status = ?
                    WHERE odoo_id = ?
                    """,
                    (
                        record.get("title", f"Review {record['id']}"),
                        record.get("branch_name"),
                        record.get("repo_url"),
                        record.get("state", "pending"),
                        status_to_write,
                        record["id"],
                    ),
                )

    def write_sync_log(self, model: str, record_count: int) -> str:
        synced_at = datetime.now(tz=UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO sync_log (model, last_synced_at, record_count)
                VALUES (?, ?, ?)
                ON CONFLICT(model) DO UPDATE SET
                    last_synced_at = excluded.last_synced_at,
                    record_count = excluded.record_count
                """,
                (model, synced_at, record_count),
            )
        return synced_at

    def get_sync_log(self) -> list[dict]:
        rows = self._connection.execute(
            "SELECT model, last_synced_at, record_count FROM sync_log ORDER BY model"
        ).fetchall()
        return [
            {
                "model": row[0],
                "last_synced_at": row[1],
                "record_count": row[2],
            }
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()
