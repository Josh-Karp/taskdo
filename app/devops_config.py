"""Loader for devops review sync configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.odoo.client import OdooClient, OdooConnectionError

logger = logging.getLogger(__name__)


class DevopsConfigError(Exception):
    """Raised when devops config is invalid."""


@dataclass(frozen=True)
class DevopsConfig:
    model: str
    filters: dict[str, str]
    fields: dict[str, str]
    repo_url: str


class DevopsConfigLoader:
    """Load and validate devops config against Odoo fields metadata."""

    def __init__(
        self,
        config_path: str | Path = "devops_config.yaml",
        client: OdooClient | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.client = client or OdooClient()

    def load(self) -> DevopsConfig:
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except FileNotFoundError as exc:
            raise DevopsConfigError(f"Missing config file: {self.config_path}") from exc

        model = raw.get("model")
        filters = raw.get("filters") or {}
        fields = raw.get("fields") or {}
        repo_url = raw.get("repo_url", "")

        if not model:
            raise DevopsConfigError("Missing config value: model")
        if not isinstance(fields, dict) or not fields:
            raise DevopsConfigError("Missing config mapping: fields")

        try:
            metadata = self.client.fields_get(model)
        except OdooConnectionError as exc:
            raise DevopsConfigError(f"Unable to validate model '{model}': {exc}") from exc

        missing = sorted(
            odoo_field
            for odoo_field in fields.values()
            if odoo_field and odoo_field not in metadata
        )
        if missing:
            missing_list = ", ".join(missing)
            logger.error("Missing fields on model '%s': %s", model, missing_list)
            raise DevopsConfigError(
                f"Fields not found on model '{model}': {missing_list}"
            )

        return DevopsConfig(
            model=model,
            filters=filters,
            fields=fields,
            repo_url=repo_url,
        )
