import socket
from unittest.mock import Mock

import pytest

from app.odoo.client import OdooAuthError, OdooClient, OdooConnectionError


def _patch_server_proxy(monkeypatch, common_proxy, object_proxy):
    def fake_server_proxy(url, allow_none=True):
        if url.endswith("/common"):
            return common_proxy
        return object_proxy

    monkeypatch.setattr("xmlrpc.client.ServerProxy", fake_server_proxy)


def test_authenticate_success(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = 3
    object_proxy = Mock()
    _patch_server_proxy(monkeypatch, common, object_proxy)

    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    uid = client.authenticate()

    assert uid == 3
    assert client.uid == 3


def test_authenticate_wrong_credentials(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = False
    object_proxy = Mock()
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    with pytest.raises(OdooAuthError):
        client.authenticate()


def test_authenticate_connection_refused(monkeypatch) -> None:
    common = Mock()
    common.authenticate.side_effect = ConnectionRefusedError("refused")
    object_proxy = Mock()
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    with pytest.raises(OdooConnectionError):
        client.authenticate()


def test_authenticate_is_cached(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = 5
    object_proxy = Mock()
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    client.authenticate()
    client.authenticate()

    assert common.authenticate.call_count == 1


def test_search_read_returns_records(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = 5
    object_proxy = Mock()
    expected = [{"id": 1, "name": "Task"}]
    object_proxy.execute_kw.return_value = expected
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    records = client.search_read("project.task", [], ["id"])

    assert records == expected


def test_search_read_connection_error(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = 5
    object_proxy = Mock()
    object_proxy.execute_kw.side_effect = OSError("down")
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    with pytest.raises(OdooConnectionError):
        client.search_read("project.task", [], ["id"])


def test_fields_get_returns_dict(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = 5
    object_proxy = Mock()
    expected = {"name": {"string": "Name"}}
    object_proxy.execute_kw.return_value = expected
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    assert client.fields_get("project.task") == expected


def test_create_returns_id(monkeypatch) -> None:
    common = Mock()
    common.authenticate.return_value = 5
    object_proxy = Mock()
    object_proxy.execute_kw.return_value = 17
    _patch_server_proxy(monkeypatch, common, object_proxy)
    client = OdooClient(url="http://odoo", db="db", user="u", password="p")

    assert client.create("project.task", {"name": "A"}) == 17

