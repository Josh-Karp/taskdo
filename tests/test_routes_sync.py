from unittest.mock import Mock
from fastapi.testclient import TestClient

from app.main import app
from app.odoo.client import OdooAuthError, OdooConnectionError


def test_post_sync_calls_worker() -> None:
    with TestClient(app) as client:
        mock_worker = Mock()
        mock_worker.run.return_value = {"status": "ok", "synced": {}}
        client.app.state.sync_worker = mock_worker

        response = client.post("/sync")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_worker.run.assert_called_once()


def test_post_sync_partial_odoo_down() -> None:
    with TestClient(app) as client:
        mock_worker = Mock()
        mock_worker.run.return_value = {"status": "partial", "synced": {"project.project": {"count": 1, "synced_at": "2026-03-18T07:45:00"}}}
        client.app.state.sync_worker = mock_worker

        response = client.post("/sync")

    assert response.status_code == 200
    assert response.json()["status"] == "partial"


def test_connection_test_success() -> None:
    with TestClient(app) as client:
        mock_client = Mock()
        mock_client.authenticate.return_value = 3
        mock_client.url = "https://your.odoo.instance"
        client.app.state.odoo_client = mock_client

        response = client.get("/settings/connection-test")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["uid"] == 3


def test_connection_test_failure() -> None:
    with TestClient(app) as client:
        mock_client = Mock()
        mock_client.authenticate.side_effect = OdooConnectionError(
            "Connection refused: https://your.odoo.instance"
        )
        mock_client.url = "https://your.odoo.instance"
        client.app.state.odoo_client = mock_client

        response = client.get("/settings/connection-test")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "Connection refused" in body["message"]


def test_connection_test_auth_failure() -> None:
    with TestClient(app) as client:
        mock_client = Mock()
        mock_client.authenticate.side_effect = OdooAuthError("Authentication failed")
        mock_client.url = "https://your.odoo.instance"
        client.app.state.odoo_client = mock_client

        response = client.get("/settings/connection-test")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "Authentication failed" in body["message"]
