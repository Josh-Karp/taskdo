import sqlite3


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
