from app.devops_config import DevopsConfig
from app.odoo.client import OdooConnectionError
from app.odoo.sync import OdooSyncWorker
from app.repository import SQLiteRepository


class OdooClientStub:
    def __init__(self) -> None:
        self._uid = 7
        self.projects = []
        self.tasks = []
        self.reviews = []
        self.raise_on_tasks = False
        self.raise_on_projects = False
        self.raise_on_reviews = False

    def authenticate(self) -> int:
        return self._uid

    def search_read(self, model: str, domain: list, fields: list[str]):
        if model == "project.project":
            if self.raise_on_projects:
                raise OdooConnectionError("down")
            return self.projects
        if model == "project.task":
            if self.raise_on_tasks:
                raise OdooConnectionError("down")
            return self.tasks
        if self.raise_on_reviews:
            raise OdooConnectionError("down")
        return self.reviews


def _task_record(task_id: int, project_id=1, stage_id="open", name: str | None = None) -> dict:
    task_name = name or f"T{task_id}"
    return {
        "id": task_id,
        "name": task_name,
        "description": "",
        "project_id": project_id,
        "date_deadline": None,
        "stage_id": stage_id,
        "date_assign": None,
        "date_last_stage_update": None,
    }


def _build_worker(repo: SQLiteRepository, client: OdooClientStub) -> OdooSyncWorker:
    config = DevopsConfig(
        model="devops.review",
        filters={
            "assigned_user_field": "user_id",
            "status_field": "state",
            "pending_review_value": "pending",
        },
        fields={"branch_field": "branch_name", "repo_field": "repository_url"},
        repo_url="https://fallback.example/repo.git",
    )
    return OdooSyncWorker(repository=repo, client=client, config=config)


def test_sync_populates_projects(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    client = OdooClientStub()
    client.projects = [
        {"id": 1, "name": "A", "active": True},
        {"id": 2, "name": "B", "active": True},
        {"id": 3, "name": "C", "active": True},
    ]
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    count = sqlite_repository._connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    log = sqlite_repository._connection.execute(
        "SELECT record_count FROM sync_log WHERE model = 'project.project'"
    ).fetchone()
    assert count == 3
    assert log[0] == 3


def test_sync_populates_tasks(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    client = OdooClientStub()
    client.tasks = [
        _task_record(10, project_id=[1, "P"], stage_id=[2, "In Progress"], name="T1"),
        _task_record(11, project_id=[1, "P"], stage_id=[2, "In Progress"], name="T2"),
        _task_record(12, project_id=[1, "P"], stage_id=[2, "In Progress"], name="T3"),
        _task_record(13, project_id=[1, "P"], stage_id=[2, "In Progress"], name="T4"),
        _task_record(14, project_id=[1, "P"], stage_id=[2, "In Progress"], name="T5"),
    ]
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    row = sqlite_repository._connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE origin = 'odoo'"
    ).fetchone()
    assert row[0] == 5


def test_sync_marks_missing_tasks_cancelled(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    sqlite_repository.upsert_tasks(
        [
            _task_record(20, project_id=[1, "P"], stage_id=[1, "Open"], name="T20"),
            _task_record(21, project_id=[1, "P"], stage_id=[1, "Open"], name="T21"),
            _task_record(22, project_id=[1, "P"], stage_id=[1, "Open"], name="T22"),
        ]
    )
    client = OdooClientStub()
    client.tasks = [
        _task_record(20, project_id=[1, "P"], stage_id=[1, "Open"], name="T20"),
        _task_record(21, project_id=[1, "P"], stage_id=[1, "Open"], name="T21"),
    ]
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    row = sqlite_repository._connection.execute(
        "SELECT state FROM tasks WHERE odoo_id = 22"
    ).fetchone()
    assert row[0] == "cancelled"


def test_sync_does_not_overwrite_confirmed_priority(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    sqlite_repository._connection.execute(
        """
        INSERT INTO tasks (odoo_id, origin, title, confirmed_priority)
        VALUES (30, 'odoo', 'Task', 1)
        """
    )
    client = OdooClientStub()
    client.tasks = [
        _task_record(30, project_id=[1, "P"], stage_id=[1, "Open"], name="Task updated")
    ]
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    row = sqlite_repository._connection.execute(
        "SELECT confirmed_priority FROM tasks WHERE odoo_id = 30"
    ).fetchone()
    assert row[0] == 1


def test_sync_populates_reviews(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    client = OdooClientStub()
    client.reviews = [
        {"id": 101, "branch_name": "feature/a", "repository_url": "https://repo/a.git"},
        {"id": 102, "branch_name": "feature/b", "repository_url": "https://repo/b.git"},
    ]
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    rows = sqlite_repository._connection.execute(
        "SELECT COUNT(*) FROM reviews WHERE review_status = 'pending'"
    ).fetchone()
    assert rows[0] == 2


def test_sync_does_not_reset_completed_review(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    sqlite_repository._connection.execute(
        """
        INSERT INTO reviews (odoo_id, title, review_result, review_status)
        VALUES (201, 'Review', 'some feedback', 'complete')
        """
    )
    client = OdooClientStub()
    client.reviews = [
        {"id": 201, "branch_name": "feature/a", "repository_url": "https://repo/a.git"}
    ]
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    row = sqlite_repository._connection.execute(
        "SELECT review_result, review_status FROM reviews WHERE odoo_id = 201"
    ).fetchone()
    assert row[0] == "some feedback"
    assert row[1] == "complete"


def test_sync_odoo_unreachable_exits_cleanly(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    sqlite_repository._connection.execute(
        "INSERT INTO projects (odoo_id, name, active) VALUES (1, 'Existing', 1)"
    )
    client = OdooClientStub()
    client.raise_on_projects = True
    worker = _build_worker(sqlite_repository, client)

    result = worker.run()

    count = sqlite_repository._connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert result["status"] == "partial"
    assert count == 1


def test_sync_partial_failure_writes_successful_models(sqlite_repository) -> None:
    sqlite_repository.initialize_schema()
    client = OdooClientStub()
    client.projects = [{"id": 1, "name": "P", "active": True}]
    client.raise_on_tasks = True
    worker = _build_worker(sqlite_repository, client)

    worker.run()

    project_log = sqlite_repository._connection.execute(
        "SELECT record_count FROM sync_log WHERE model='project.project'"
    ).fetchone()
    task_log = sqlite_repository._connection.execute(
        "SELECT record_count FROM sync_log WHERE model='project.task'"
    ).fetchone()
    assert project_log[0] == 1
    assert task_log is None


def test_duplicate_threshold_env_var(sqlite_repository, monkeypatch) -> None:
    sqlite_repository.initialize_schema()
    monkeypatch.setenv("DUPLICATE_THRESHOLD", "92")
    client = OdooClientStub()

    worker = _build_worker(sqlite_repository, client)

    assert worker.duplicate_threshold == 92
