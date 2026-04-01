"""
FastAPI application factory.

Usage:
    app = create_app()
    uvicorn.run(app, ...)

All routes are registered under /api/v1. The auth middleware is applied
globally. Lifespan handles DB engine startup/shutdown.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.middleware.auth import AuthMiddleware
from src.config import get_settings
from src.logging_config import configure_logging, get_logger
from src.storage.database import engine

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: verify DB is reachable. Shutdown: dispose engine."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting meeting-agent API")

    # Verify DB connection on startup
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as exc:
        logger.error("Database connection failed on startup", exc_info=exc)

    yield

    await engine.dispose()
    logger.info("Database engine disposed — shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meeting Agent — Jira-Copilot Engineering Intelligence",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    # ---------------------------------------------------------------------------
    # Middleware
    # ---------------------------------------------------------------------------

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthMiddleware)

    # ---------------------------------------------------------------------------
    # Exception handlers
    # ---------------------------------------------------------------------------

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Resource not found."})

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    # ---------------------------------------------------------------------------
    # Health probe (no auth required)
    # ---------------------------------------------------------------------------

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    # ---------------------------------------------------------------------------
    # Route registration — /api/v1
    # ---------------------------------------------------------------------------
    # Routes are imported lazily here to avoid circular imports at module load time.
    # Each route module is implemented in its own Phase task.

    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Import and include all route modules under /api/v1."""
    from importlib import import_module

    _route_modules = [
        ("src.api.routes.tickets", "/api/v1", ["tickets"]),
        ("src.api.routes.velocity", "/api/v1", ["velocity"]),
        ("src.api.routes.suggestions", "/api/v1", ["suggestions"]),
        ("src.api.routes.reports", "/api/v1", ["reports"]),
        ("src.api.routes.query", "/api/v1", ["query"]),
        ("src.api.routes.audit", "/api/v1", ["audit"]),
        ("src.api.routes.sync", "/api/v1", ["sync"]),
    ]

    for module_path, prefix, tags in _route_modules:
        try:
            module = import_module(module_path)
            router = getattr(module, "router", None)
            if router is not None:
                app.include_router(router, prefix=prefix, tags=tags)
        except ImportError:
            # Route modules are implemented phase-by-phase; silently skip unimplemented ones.
            logger.debug("Route module not yet implemented: %s", module_path)
