"""
APScheduler configuration — runs pipeline resume and notification jobs.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings

log = logging.getLogger("scheduler")


def pipeline_daily_resume():
    """Daily job: resume all active batches."""
    log.info("=== Daily pipeline resume started ===")
    from db import SessionLocal
    from models import Batch
    from pipeline.orchestrator import resume_batch

    db = SessionLocal()
    try:
        active_batches = db.query(Batch).filter(
            Batch.status.notin_(["complete", "paused"])
        ).all()

        for batch in active_batches:
            log.info("Resuming batch %d: %s (status=%s)", batch.id, batch.name, batch.status)
            try:
                resume_batch(batch.id)
            except Exception as e:
                log.error("Batch %d failed: %s", batch.id, e)
    finally:
        db.close()
    log.info("=== Daily pipeline resume complete ===")


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler with configured jobs."""
    scheduler = BackgroundScheduler()

    # Daily pipeline resume
    scheduler.add_job(
        pipeline_daily_resume,
        trigger=CronTrigger(
            hour=settings.PIPELINE_CRON_HOUR,
            minute=settings.PIPELINE_CRON_MINUTE,
        ),
        id="pipeline_daily_resume",
        name="Daily Pipeline Resume",
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "Scheduler started — pipeline runs daily at %02d:%02d UTC",
        settings.PIPELINE_CRON_HOUR,
        settings.PIPELINE_CRON_MINUTE,
    )
    return scheduler
