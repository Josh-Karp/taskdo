from collections.abc import Iterator

import pytest

from app.repository import SQLiteRepository


@pytest.fixture
def sqlite_repository() -> Iterator[SQLiteRepository]:
    repository = SQLiteRepository(":memory:")
    yield repository
    repository.close()
