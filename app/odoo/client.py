"""Odoo XML-RPC client wrapper."""

from __future__ import annotations

import os
import socket
import xmlrpc.client


class OdooConnectionError(Exception):
    """Raised when Odoo is unreachable."""


class OdooAuthError(Exception):
    """Raised when Odoo authentication fails."""


class OdooClient:
    """Client for Odoo XML-RPC endpoints."""

    def __init__(
        self,
        url: str | None = None,
        db: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.url = (url or os.getenv("ODOO_URL", "")).rstrip("/")
        self.db = db or os.getenv("ODOO_DB", "")
        self.user = user or os.getenv("ODOO_USER", "")
        self.password = password or os.getenv("ODOO_PASSWORD", "")
        self.uid: int | None = None

    def _call(self, service: str, method: str, *args):
        endpoint = f"{self.url}/xmlrpc/2/{service}"
        proxy = xmlrpc.client.ServerProxy(endpoint, allow_none=True)
        try:
            return getattr(proxy, method)(*args)
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            raise OdooConnectionError(str(exc)) from exc
        except xmlrpc.client.Fault as exc:
            fault = (exc.faultString or "").lower()
            if "access" in fault or "auth" in fault or "login" in fault:
                raise OdooAuthError(exc.faultString) from exc
            raise OdooConnectionError(exc.faultString) from exc

    def authenticate(self) -> int:
        if self.uid is not None:
            return self.uid
        uid = self._call("common", "authenticate", self.db, self.user, self.password, {})
        if not uid:
            raise OdooAuthError("Authentication failed")
        self.uid = int(uid)
        return self.uid

    def search_read(self, model: str, domain: list, fields: list[str]) -> list[dict]:
        uid = self.authenticate()
        try:
            records = self._call(
                "object",
                "execute_kw",
                self.db,
                uid,
                self.password,
                model,
                "search_read",
                [domain],
                {"fields": fields},
            )
        except OdooConnectionError as exc:
            lowered = str(exc).lower()
            if "auth" in lowered or "access" in lowered:
                raise OdooAuthError(str(exc)) from exc
            raise
        if not isinstance(records, list):
            return []
        return records

    def fields_get(self, model: str) -> dict:
        uid = self.authenticate()
        return self._call(
            "object",
            "execute_kw",
            self.db,
            uid,
            self.password,
            model,
            "fields_get",
            [],
            {},
        )

    def create(self, model: str, values: dict) -> int:
        uid = self.authenticate()
        return int(
            self._call(
                "object",
                "execute_kw",
                self.db,
                uid,
                self.password,
                model,
                "create",
                [values],
            )
        )

