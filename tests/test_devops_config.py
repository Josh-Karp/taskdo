from pathlib import Path

import pytest

from app.devops_config import DevopsConfigError, DevopsConfigLoader
from app.odoo.client import OdooConnectionError


def test_valid_config_passes(tmp_path: Path) -> None:
    config_path = tmp_path / "devops_config.yaml"
    config_path.write_text(
        """
model: devops.review
filters:
  assigned_user_field: user_id
  status_field: state
  pending_review_value: pending
fields:
  branch_field: branch_name
  repo_field: repository_url
repo_url: https://repo.example
""".strip()
    )

    class ClientStub:
        def fields_get(self, model: str):
            return {"branch_name": {}, "repository_url": {}, "state": {}, "user_id": {}}

    loader = DevopsConfigLoader(config_path=config_path, client=ClientStub())

    config = loader.load()

    assert config.model == "devops.review"
    assert config.fields["branch_field"] == "branch_name"
    assert config.repo_url == "https://repo.example"


def test_missing_field_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "devops_config.yaml"
    config_path.write_text(
        """
model: devops.review
filters:
  assigned_user_field: user_id
  status_field: state
  pending_review_value: pending
fields:
  branch_field: missing_branch
repo_url: https://repo.example
""".strip()
    )

    class ClientStub:
        def fields_get(self, model: str):
            return {"state": {}, "user_id": {}}

    loader = DevopsConfigLoader(config_path=config_path, client=ClientStub())

    with pytest.raises(DevopsConfigError, match="missing_branch"):
        loader.load()


def test_invalid_model_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "devops_config.yaml"
    config_path.write_text(
        """
model: devops.review
filters:
  assigned_user_field: user_id
  status_field: state
  pending_review_value: pending
fields:
  branch_field: branch_name
repo_url: https://repo.example
""".strip()
    )

    class ClientStub:
        def fields_get(self, model: str):
            raise OdooConnectionError("connection failed")

    loader = DevopsConfigLoader(config_path=config_path, client=ClientStub())

    with pytest.raises(DevopsConfigError, match="Unable to validate model"):
        loader.load()


def test_optional_repo_field_absent(tmp_path: Path) -> None:
    config_path = tmp_path / "devops_config.yaml"
    config_path.write_text(
        """
model: devops.review
filters:
  assigned_user_field: user_id
  status_field: state
  pending_review_value: pending
fields:
  branch_field: branch_name
repo_url: https://repo.example
""".strip()
    )

    class ClientStub:
        def fields_get(self, model: str):
            return {"branch_name": {}, "state": {}, "user_id": {}}

    loader = DevopsConfigLoader(config_path=config_path, client=ClientStub())

    config = loader.load()

    assert "repo_field" not in config.fields

