from __future__ import annotations

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from crd_notes import __version__
from crd_notes.api import router
from crd_notes.app_state import job_runner
from crd_notes.core.errors import AiConnectorError, CrdNotesError
from crd_notes.core.logging import configure_logging
from crd_notes.core.paths import WEB_DIR, ensure_data_dirs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    job_runner.start()
    yield


def create_app() -> FastAPI:
    ensure_data_dirs()
    configure_logging()
    app = FastAPI(title="crd-notes", version=__version__, lifespan=lifespan)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.exception_handler(CrdNotesError)
    async def crd_error_handler(_request: Request, exc: CrdNotesError) -> JSONResponse:
        status_code = 502 if isinstance(exc, AiConnectorError) else 400
        return JSONResponse(
            status_code=status_code,
            content={"message": exc.message, "detail": exc.detail},
        )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    return app


def run() -> None:
    host = os.environ.get("CRD_NOTES_HOST", "127.0.0.1")
    port = int(os.environ.get("CRD_NOTES_PORT", "8184"))
    reload = os.environ.get("CRD_NOTES_RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run(
        "crd_notes.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
