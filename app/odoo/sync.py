"""Odoo read sync worker."""

from __future__ import annotations

import logging
import os

from app.devops_config import DevopsConfig
from app.odoo.client import OdooClient, OdooConnectionError
from app.repository import SQLiteRepository

logger = logging.getLogger(__name__)


class OdooSyncWorker:
    """Coordinates Odoo -> SQLite synchronisation."""

    def __init__(
        self,
        repository: SQLiteRepository,
        client: OdooClient,
        config: DevopsConfig,
    ) -> None:
        self.repository = repository
        self.client = client
        self.config = config
        self.duplicate_threshold = int(os.getenv("DUPLICATE_THRESHOLD", "85"))

    def run(self) -> dict:
        synced: dict[str, dict[str, object]] = {}
        status = "ok"

        try:
            project_count = self._sync_projects()
            synced_at = self.repository.write_sync_log("project.project", project_count)
            synced["project.project"] = {"count": project_count, "synced_at": synced_at}
        except OdooConnectionError as exc:
            logger.error("Odoo projects sync failed: %s", exc)
            return {"status": "partial", "synced": synced}
        except Exception as exc:  # pragma: no cover - defensive log path
            logger.exception("Unexpected projects sync error: %s", exc)
            status = "partial"

        try:
            task_count = self._sync_tasks()
            synced_at = self.repository.write_sync_log("project.task", task_count)
            synced["project.task"] = {"count": task_count, "synced_at": synced_at}
        except OdooConnectionError as exc:
            logger.error("Odoo tasks sync failed: %s", exc)
            return {"status": "partial", "synced": synced}
        except Exception as exc:  # pragma: no cover - defensive log path
            logger.exception("Unexpected tasks sync error: %s", exc)
            status = "partial"

        try:
            review_model = self.config.model
            review_count = self._sync_reviews()
            synced_at = self.repository.write_sync_log(review_model, review_count)
            synced[review_model] = {"count": review_count, "synced_at": synced_at}
        except OdooConnectionError as exc:
            logger.error("Odoo reviews sync failed: %s", exc)
            return {"status": "partial", "synced": synced}
        except Exception as exc:  # pragma: no cover - defensive log path
            logger.exception("Unexpected reviews sync error: %s", exc)
            status = "partial"

        self._drain_push_queue()
        return {"status": status, "synced": synced}

    def _sync_projects(self) -> int:
        records = self.client.search_read(
            "project.project",
            [("active", "=", True)],
            ["id", "name", "active"],
        )
        self.repository.upsert_projects(records)
        return len(records)

    def _sync_tasks(self) -> int:
        uid = self.client.authenticate()
        records = self.client.search_read(
            "project.task",
            [
                ("user_ids", "in", [uid]),
                ("active", "=", True),
                ("stage_id.closed", "=", False),
            ],
            [
                "id",
                "name",
                "description",
                "project_id",
                "date_deadline",
                "stage_id",
                "date_assign",
                "date_last_stage_update",
            ],
        )
        self.repository.upsert_tasks(records)
        self.repository.mark_tasks_cancelled([record["id"] for record in records])
        return len(records)

    def _sync_reviews(self) -> int:
        uid = self.client.authenticate()
        fields = [
            "id",
            self.config.fields["branch_field"],
        ]
        repo_field_name = self.config.fields.get("repo_field")
        if repo_field_name:
            fields.append(repo_field_name)
        records = self.client.search_read(
            self.config.model,
            [
                (self.config.filters["assigned_user_field"], "=", uid),
                (
                    self.config.filters["status_field"],
                    "=",
                    self.config.filters["pending_review_value"],
                ),
            ],
            fields,
        )
        transformed = []
        for record in records:
            transformed.append(
                {
                    "id": record["id"],
                    "title": f"Review {record['id']}",
                    "branch_name": record.get(self.config.fields["branch_field"]),
                    "repo_url": (
                        record.get(repo_field_name)
                        if repo_field_name
                        else self.config.repo_url
                    ),
                    "state": "pending",
                }
            )
        self.repository.upsert_reviews(transformed)
        return len(records)

    def _drain_push_queue(self) -> None:
        return None

