from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.mark.parametrize("endpoint", ["/health", "/healthz"])
def test_health_endpoints_return_database_status(endpoint: str) -> None:
    with TestClient(app) as client:
        response = client.get(endpoint)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}
