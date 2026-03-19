import sqlite3

import pytest


def test_initialize_schema_creates_all_tables(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()

    rows = sqlite_repository._connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    table_names = {row[0] for row in rows}

    assert {
        "tasks",
        "projects",
        "reviews",
        "sync_log",
        "push_queue",
        "daily_summary",
    }.issubset(table_names)


def test_initialize_schema_is_idempotent(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    sqlite_repository.initialize_schema()

    rows = sqlite_repository._connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    table_names = [row[0] for row in rows]

    assert table_names.count("tasks") == 1
    assert table_names.count("projects") == 1
    assert table_names.count("reviews") == 1
    assert table_names.count("sync_log") == 1
    assert table_names.count("push_queue") == 1
    assert table_names.count("daily_summary") == 1


def test_foreign_key_constraints_are_enforced(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()

    with pytest.raises(sqlite3.IntegrityError):
        sqlite_repository._connection.execute(
            """
            INSERT INTO push_queue (task_id, status, duplicate_candidate_odoo_id)
            VALUES (999, 'pending', NULL)
            """
        )


def test_initialize_schema_creates_unique_indexes_for_odoo_id(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()

    indexes = sqlite_repository._connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    index_names = {row[0] for row in indexes}

    assert "idx_tasks_odoo_id" in index_names
    assert "idx_projects_odoo_id" in index_names
    assert "idx_reviews_odoo_id" in index_names


def test_initialize_schema_adds_indexes_to_existing_tables_without_unique_constraints(
    sqlite_repository,
) -> None:
    with sqlite_repository._connection:
        sqlite_repository._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER,
                origin TEXT NOT NULL CHECK (origin IN ('odoo', 'local')),
                title TEXT NOT NULL
            )
            """
        )
        sqlite_repository._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        sqlite_repository._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                odoo_id INTEGER,
                title TEXT NOT NULL,
                review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'complete', 'failed'))
            )
            """
        )

    sqlite_repository.initialize_schema()

    with sqlite_repository._connection:
        sqlite_repository._connection.execute(
            "INSERT INTO tasks (odoo_id, origin, title) VALUES (?, 'odoo', ?)",
            (101, "Task A"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            sqlite_repository._connection.execute(
                "INSERT INTO tasks (odoo_id, origin, title) VALUES (?, 'odoo', ?)",
                (101, "Task B"),
            )
