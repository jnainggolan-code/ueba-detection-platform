"""FastAPI application entry point for UEBA Detection Platform."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import events as events_v1
from app.api.v1 import health as health_v1
from app.api.v2 import ingest as ingest_v2
from app.api.v2 import process as process_v2
from app.api.v2 import wazuh as wazuh_v2

# Setup logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="UEBA Detection Platform API — Ingestion & Analysis",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    origins = (
        settings.cors_origins.split(",")
        if settings.cors_origins != "*"
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(events_v1.router)
    app.include_router(health_v1.router)
    app.include_router(ingest_v2.router)
    app.include_router(process_v2.router)
    app.include_router(wazuh_v2.router)

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "Starting %s v%s", settings.app_name, settings.app_version
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Shutting down %s", settings.app_name)

    return app


app = create_app()
