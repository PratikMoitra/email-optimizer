"""
Webhook event emitter — fires events to user-configured URLs.
HMAC-signed payloads with retry logic.
"""

import json
import hmac
import hashlib
import logging
import time
from datetime import datetime

import requests

from db import SessionLocal
from models import Profile, WebhookEvent

log = logging.getLogger("webhooks")

MAX_RETRIES = 3
RETRY_DELAYS = [5, 30, 120]  # seconds


def emit(user_id: str, event_type: str, payload: dict, batch_id: int = None):
    """
    Fire a webhook event to the user's configured URL.
    Stores the event in webhook_events table and attempts delivery.
    """
    db = SessionLocal()
    try:
        user = db.query(Profile).filter(Profile.id == user_id).first()
        if not user or not user.webhook_url:
            log.debug("No webhook URL for user %s, skipping event %s", user_id, event_type)
            return

        # Build event envelope
        event_data = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": payload,
        }

        # Store in DB
        event = WebhookEvent(
            user_id=user_id,
            batch_id=batch_id,
            event_type=event_type,
            payload=event_data,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Attempt delivery
        _deliver(event, user.webhook_url, user.webhook_secret)
        db.commit()

    except Exception as e:
        log.error("Failed to emit webhook event %s: %s", event_type, e)
        db.rollback()
    finally:
        db.close()


def _deliver(event: WebhookEvent, url: str, secret: str = None):
    """Deliver a webhook event with HMAC signing and retries."""
    body = json.dumps(event.payload, default=str)

    headers = {"Content-Type": "application/json"}
    if secret:
        signature = hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    for attempt in range(MAX_RETRIES):
        event.attempts = attempt + 1
        try:
            resp = requests.post(url, data=body, headers=headers, timeout=30)
            event.response_status = resp.status_code
            if resp.status_code < 300:
                event.delivered = True
                log.info("Webhook delivered: %s → %d", event.event_type, resp.status_code)
                return
            log.warning(
                "Webhook %s attempt %d: HTTP %d", event.event_type, attempt + 1, resp.status_code
            )
        except requests.RequestException as e:
            log.warning("Webhook %s attempt %d failed: %s", event.event_type, attempt + 1, e)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAYS[attempt])

    log.error("Webhook %s failed after %d attempts", event.event_type, MAX_RETRIES)


def retry_failed_events():
    """Retry all undelivered webhook events (called by scheduler)."""
    db = SessionLocal()
    try:
        pending = db.query(WebhookEvent).filter(
            WebhookEvent.delivered == False,  # noqa: E712
            WebhookEvent.attempts < MAX_RETRIES,
        ).all()

        for event in pending:
            user = db.query(Profile).filter(Profile.id == event.user_id).first()
            if user and user.webhook_url:
                _deliver(event, user.webhook_url, user.webhook_secret)
                db.commit()
    finally:
        db.close()
