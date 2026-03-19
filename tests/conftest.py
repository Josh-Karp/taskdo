from collections.abc import Iterator

import pytest

from app.repository import SQLiteRepository


@pytest.fixture
def sqlite_repository() -> Iterator[SQLiteRepository]:
    repository = SQLiteRepository(":memory:")
    yield repository
    repository.close()


@pytest.fixture(autouse=True)
def stub_odoo_for_app_startup(monkeypatch):
    class ClientStub:
        def __init__(self) -> None:
            self.url = "https://stub.odoo"

        def fields_get(self, model: str):
            return {"branch_name": {}, "repository_url": {}, "user_id": {}, "state": {}}

        def authenticate(self) -> int:
            return 1

    monkeypatch.setattr("app.main.OdooClient", ClientStub)
