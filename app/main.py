"""FastAPI entrypoint for Taskdo."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.repository import SQLiteRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.repository = SQLiteRepository("/data/db.sqlite")
    repository: SQLiteRepository = app.state.repository
    repository.initialize_schema()
    scheduler = BackgroundScheduler()
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
