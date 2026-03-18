"""FastAPI entrypoint for Taskdo."""

from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.repository import SQLiteRepository

app = FastAPI(title="taskdo")
scheduler = BackgroundScheduler()
repository = SQLiteRepository("/data/db.sqlite")


@app.on_event("startup")
def startup() -> None:
    repository.initialize_schema()
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    repository.close()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    repository.is_reachable()
    return {"status": "ok", "database": "reachable"}


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
