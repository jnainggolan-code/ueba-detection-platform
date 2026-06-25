"""RQ worker entry point — consumes engine-pipeline jobs from Redis queue.

Usage:
    python -m app.worker

Runs workers on the 'engine-pipeline' queue with configurable concurrency.
Each job processes one event through anomaly detection + risk scoring.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Any

import redis
from rq import Worker, Queue, Connection

from app.core.config import settings
from app.core.redis import get_sync_redis
from app.db.session import background_session_factory
from app.models.event import LogsRaw
from app.services.anomaly_detector import AnomalyDetector
from app.services.risk_scoring import RiskScoringService

logger = logging.getLogger(__name__)

# Semaphore to cap concurrent engine pipeline executions per worker process
_pipeline_semaphore = asyncio.Semaphore(5)


def run_engine_pipeline(event_data: dict) -> dict:
    """Sync wrapper: run anomaly detection + risk scoring for a serialized event.

    Called by RQ worker for each job in the 'engine-pipeline' queue.

    Args:
        event_data: Serialized LogsRaw dict (from __json__ export).

    Returns:
        Dict with result summary.
    """
    event_id = event_data.get("id")
    logger.info("Engine pipeline started for event id=%s", event_id)

    try:
        result = asyncio.run(_run_pipeline_async(event_data))
        logger.info("Engine pipeline completed for event id=%s", event_id)
        return result
    except Exception as exc:
        logger.error(
            "Engine pipeline failed for event id=%s: %s",
            event_id, exc, exc_info=True,
        )
        return {"event_id": event_id, "status": "error", "error": str(exc)}


async def _run_pipeline_async(event_data: dict) -> dict:
    """Async core: run pipeline with semaphore-controlled concurrency."""
    async with _pipeline_semaphore:
        async with background_session_factory() as session:
            try:
                # Reconstruct LogsRaw from serialized data
                event = LogsRaw(**event_data)

                # Merge into current session context
                merged = await session.merge(event)

                detector = AnomalyDetector(session)
                scorer = RiskScoringService(session)

                # Step 1: Detect anomalies
                anomalies = await detector.detect_anomalies(merged)
                if anomalies:
                    logger.info(
                        "Detected %d anomalies for event id=%s",
                        len(anomalies), merged.id,
                    )

                # Step 2: Update risk score
                risk_result = await scorer.update_risk_score(merged)
                logger.debug(
                    "Risk score updated for event id=%s: score=%s",
                    merged.id, risk_result.get("overall_score"),
                )

                await session.commit()

                return {
                    "event_id": merged.id,
                    "status": "completed",
                    "anomalies_count": len(anomalies) if anomalies else 0,
                    "risk_score": risk_result.get("overall_score"),
                }
            except Exception:
                await session.rollback()
                raise


def setup_logging() -> None:
    """Configure logging for the worker process."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def main() -> None:
    """Start RQ worker listening on the 'engine-pipeline' queue."""
    setup_logging()
    logger.info("Starting RQ worker for queue 'engine-pipeline'")

    # Connect to Redis
    r = get_sync_redis()

    with Connection(r):
        worker = Worker(
            queues=["engine-pipeline"],
            connection=r,
            name="detection-worker",
            logging_level=logging.getLevelName(logger.level),
        )

        # Handle graceful shutdown
        shutdown_event = asyncio.Event()

        def _handle_signal(signum, frame):
            logger.info("Received signal %s, shutting down...", signum)
            shutdown_event.set()
            worker.shutdown()

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        logger.info(
            "Worker ready. Listening on queue(s): %s",
            ", ".join(worker.queue_names()),
        )
        worker.work(
            with_scheduler=False,
            max_jobs=None,
            burst=False,
        )


if __name__ == "__main__":
    main()
