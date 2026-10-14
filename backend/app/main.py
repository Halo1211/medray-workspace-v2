import sqlite3

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.ai_setup.local import router as local_setup_router
from app.ai_setup.routes import router as setup_router
from app.api.routes import router
from app.config import get_settings
from app.runtime.secrets import safe_error
from app.storage.db import CaseConflictError, CaseNotFoundError, init_db


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    @app.exception_handler(CaseConflictError)
    async def case_conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(CaseNotFoundError)
    async def missing_case(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Case no longer exists."})

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "The database is busy or unavailable. Close duplicate MedRay sessions, check storage permissions, then retry. Your saved cases have not been replaced."})

    @app.exception_handler(OSError)
    async def storage_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": safe_error(exc)})

    @app.exception_handler(ValidationError)
    @app.exception_handler(RequestValidationError)
    async def invalid_configuration(request, exc):
        # Do not return Pydantic's raw input values (tokens or patient metadata).
        return JSONResponse(status_code=422 if isinstance(exc, RequestValidationError) else 400, content={"detail": "Some fields are invalid. Check the selected settings and required values, then retry."})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(setup_router, prefix="/api")
    app.include_router(local_setup_router, prefix="/api")
    return app


app = create_app()
