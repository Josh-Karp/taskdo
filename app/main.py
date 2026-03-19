"""FastAPI entrypoint for Taskdo."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.devops_config import DevopsConfig, DevopsConfigError, DevopsConfigLoader
from app.odoo.client import OdooAuthError, OdooClient, OdooConnectionError
from app.odoo.sync import OdooSyncWorker
from app.repository import SQLiteRepository
from app.scheduler import AppScheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.repository = SQLiteRepository("/data/db.sqlite")
    repository: SQLiteRepository = app.state.repository
    repository.initialize_schema()
    client = OdooClient()
    app.state.odoo_client = client
    config = _load_devops_config(client)
    app.state.devops_config = config
    app.state.sync_worker = OdooSyncWorker(repository=repository, client=client, config=config)
    scheduler = AppScheduler()
    scheduler.register_sync_job(app.state.sync_worker.run)
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        repository.close()


app = FastAPI(title="taskdo", lifespan=lifespan)


@app.get("/health")
@app.get("/healthz")
def health(request: Request) -> dict[str, str]:
    repository: SQLiteRepository = request.app.state.repository
    repository.is_reachable()
    return {"status": "ok", "database": "reachable"}


@app.post("/sync")
def sync(request: Request) -> dict:
    worker: OdooSyncWorker = request.app.state.sync_worker
    try:
        result = worker.run()
    except OdooConnectionError as exc:
        logger.error("Sync connection failure: %s", exc)
        return {"status": "partial", "synced": {}}
    return result


@app.get("/settings/connection-test")
def connection_test(request: Request) -> dict:
    client: OdooClient = request.app.state.odoo_client
    try:
        uid = client.authenticate()
    except OdooAuthError as exc:
        return {"status": "error", "message": str(exc)}
    except OdooConnectionError as exc:
        return {"status": "error", "message": f"{exc}"}
    except DevopsConfigError as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "odoo_url": client.url, "uid": uid}


def _load_devops_config(client: OdooClient) -> DevopsConfig:
    config_loader = DevopsConfigLoader(client=client)
    return config_loader.load()


frontend_dist_candidates = [
    Path("/app/frontend_dist"),
    Path(__file__).resolve().parents[1] / "frontend" / "dist",
]
frontend_dist = next((path for path in frontend_dist_candidates if path.exists()), None)
if frontend_dist and (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    index_file = frontend_dist / "index.html" if frontend_dist else None
    if index_file and index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return """
    <!DOCTYPE html>
    <html>
      <head><title>taskdo</title></head>
      <body>
        <div id='root'>Taskdo placeholder frontend</div>
      </body>
    </html>
    """
