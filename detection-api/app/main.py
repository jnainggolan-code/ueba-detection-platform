"""FastAPI application entry point for UEBA Detection Platform."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import init_redis, close_redis
from app.middleware.rate_limiter import RateLimitMiddleware
from app.api.v1 import events as events_v1
from app.api.v1 import health as health_v1
from app.api.v1 import stats as stats_v1
from app.api.v1 import entities as entities_v1
from app.api.v1 import alerts as alerts_v1
from app.api.v1 import rules as rules_v1
from app.api.v1 import engine as engine_v1
from app.api.v2 import ingest as ingest_v2
from app.api.v2 import process as process_v2
from app.api.v2 import wazuh as wazuh_v2
from app.api.v2 import delinea as delinea_v2
from app.api.v2 import cortexxdr as cortexxdr_v2

# Setup logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init Redis on startup, close on shutdown."""
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    await init_redis()
    yield
    await close_redis()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="UEBA Detection Platform API — Ingestion & Analysis",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
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

    # Rate Limiter
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=100,
        window_seconds=60,
    )

    # Register routers
    app.include_router(events_v1.router)
    app.include_router(health_v1.router)
    app.include_router(stats_v1.router)
    app.include_router(entities_v1.router)
    app.include_router(alerts_v1.router)
    app.include_router(engine_v1.router)
    app.include_router(ingest_v2.router)
    app.include_router(process_v2.router)
    app.include_router(wazuh_v2.router)
    app.include_router(delinea_v2.router)
    app.include_router(cortexxdr_v2.router)
    app.include_router(rules_v1.router)

    return app


app = create_app()
