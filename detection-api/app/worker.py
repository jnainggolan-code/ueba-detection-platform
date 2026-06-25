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
from rq import Worker, Queue

from app.core.redis import get_sync_redis
from app.db.session import background_session_factory
from app.services.anomaly_detector import AnomalyDetector
from app.services.risk_scoring import RiskScoringService
from app.services.rule_engine import RuleEngineService

logger = logging.getLogger(__name__)

# Semaphore to cap concurrent engine pipeline executions per worker process
_pipeline_semaphore = asyncio.Semaphore(5)


def run_engine_pipeline(event_id: int) -> dict:
    """Sync wrapper: run anomaly detection + risk scoring for an event by ID.

    Called by RQ worker for each job in the 'engine-pipeline' queue.
    Fetches the event from DB by ID to avoid serialization issues.

    Args:
        event_id: ID of the LogsRaw event to process.

    Returns:
        Dict with result summary.
    """
    logger.info("Engine pipeline started for event id=%s", event_id)

    try:
        result = asyncio.run(_run_pipeline_async(event_id))
        logger.info("Engine pipeline completed for event id=%s", event_id)
        return result
    except Exception as exc:
        logger.error(
            "Engine pipeline failed for event id=%s: %s",
            event_id, exc, exc_info=True,
        )
        return {"event_id": event_id, "status": "error", "error": str(exc)}


async def _run_pipeline_async(event_id: int) -> dict:
    """Async core: run pipeline with semaphore-controlled concurrency."""
    async with _pipeline_semaphore:
        async with background_session_factory() as session:
            try:
                from sqlalchemy import select
                from app.db.repositories.event_repo import EventRepository

                # Fetch event from DB by ID
                repo = EventRepository(session)
                event = await repo.find_by_id(event_id)
                if not event:
                    logger.error("Event id=%s not found in DB", event_id)
                    return {"event_id": event_id, "status": "error", "error": "Event not found"}

                detector = AnomalyDetector(session)
                scorer = RiskScoringService(session)

                # Step 1: Detect anomalies
                anomalies = await detector.detect_anomalies(event)
                if anomalies:
                    logger.info(
                        "Detected %d anomalies for event id=%s",
                        len(anomalies), event.id,
                    )

                # Step 2: Update risk score
                risk_result = await scorer.update_risk_score(event)
                logger.debug(
                    "Risk score updated for event id=%s: score=%s",
                    event.id, risk_result.get("overall_score"),
                )

                # Step 3: Evaluate custom rules
                try:
                    rule_engine = RuleEngineService(session)
                    triggered = await rule_engine.evaluate_all_rules(event, risk_result)
                    if triggered:
                        logger.info(
                            "Rule engine triggered %d alerts for event id=%s",
                            len(triggered), event.id
                        )
                except Exception as rule_exc:
                    logger.error(
                        "Rule evaluation error for event id=%s: %s",
                        event.id, rule_exc, exc_info=True
                    )

                await session.commit()

                return {
                    "event_id": event.id,
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

    worker = Worker(
        queues=["engine-pipeline"],
        connection=r,
        name="detection-worker",
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
