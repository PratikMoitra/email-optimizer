"""
FastAPI application entry point.
Mounts all API routes and starts the scheduler.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import engine, Base
from security.auth_routes import router as auth_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("email-optimizer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables + start scheduler. Shutdown: stop scheduler."""
    # Create tables if they don't exist (dev convenience)
    import models  # noqa: F401 — registers models with Base
    Base.metadata.create_all(bind=engine)
    log.info("Database tables verified")

    # Start scheduler
    from scheduler import start_scheduler
    scheduler = start_scheduler()
    log.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown()
    log.info("Scheduler stopped")


app = FastAPI(
    title="Email Optimizer",
    description="AI-powered cold email campaign automation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.APP_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount auth routes (Google OAuth, API key management)
app.include_router(auth_router)


# --- API Routes ---

@app.get("/health")
async def health():
    return {"status": "ok", "service": "email-optimizer-backend"}


@app.get("/api/credits")
async def get_credits():
    """Check available credits for Vayne and Anymailfinder."""
    # TODO: implement per-user credit check
    return {"vayne": {"available": 0}, "anymailfinder": {"available": 0}}


@app.get("/api/batches")
async def list_batches():
    """List all batches for the current user."""
    # TODO: implement with auth
    from db import SessionLocal
    from models import Batch
    db = SessionLocal()
    try:
        batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
        return {
            "batches": [
                {
                    "id": b.id,
                    "name": b.name,
                    "status": b.status,
                    "total_leads": b.total_leads,
                    "leads_valid": b.leads_valid,
                    "leads_deployed": b.leads_deployed,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                }
                for b in batches
            ]
        }
    finally:
        db.close()


@app.post("/api/batches")
async def create_batch(data: dict):
    """Create a new pipeline batch from a Sales Navigator URL."""
    # TODO: implement full pipeline trigger
    return {"status": "created", "batch_id": 0}


@app.get("/api/batches/{batch_id}")
async def get_batch(batch_id: int):
    """Get batch details including lead progress."""
    from db import SessionLocal
    from models import Batch, Lead
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            return {"error": "Batch not found"}, 404

        leads = db.query(Lead).filter(Lead.batch_id == batch_id).all()
        return {
            "batch": {
                "id": batch.id,
                "name": batch.name,
                "status": batch.status,
                "total_leads": batch.total_leads,
                "leads_validated": batch.leads_validated,
                "leads_valid": batch.leads_valid,
                "leads_researched": batch.leads_researched,
                "leads_generated": batch.leads_generated,
                "leads_deployed": batch.leads_deployed,
            },
            "leads": [
                {
                    "id": l.id,
                    "first_name": l.first_name,
                    "last_name": l.last_name,
                    "company_name": l.company_name,
                    "email": l.email,
                    "stage": l.stage,
                    "industry": l.industry,
                }
                for l in leads
            ],
        }
    finally:
        db.close()


@app.get("/api/webhook-config")
async def get_webhook_config(user_id: str):
    """Get webhook configuration for a user."""
    from db import SessionLocal
    from models import Profile
    db = SessionLocal()
    try:
        user = db.query(Profile).filter(Profile.id == user_id).first()
        if not user:
            return {"configured": False}
        return {
            "configured": bool(user.webhook_url),
            "url": user.webhook_url or "",
            "has_secret": bool(user.webhook_secret),
        }
    finally:
        db.close()


@app.post("/api/webhook-config")
async def save_webhook_config(data: dict):
    """Save webhook URL and optional secret for a user."""
    from db import SessionLocal
    from models import Profile
    user_id = data.get("user_id")
    webhook_url = data.get("url", "").strip()
    webhook_secret = data.get("secret", "").strip()

    db = SessionLocal()
    try:
        user = db.query(Profile).filter(Profile.id == user_id).first()
        if not user:
            # Create profile if doesn't exist (dev convenience)
            user = Profile(id=user_id, email=f"{user_id}@dev.local")
            db.add(user)

        user.webhook_url = webhook_url or None
        user.webhook_secret = webhook_secret or None
        db.commit()
        return {"status": "saved", "url": webhook_url}
    finally:
        db.close()


@app.post("/api/webhook-test")
async def test_webhook(data: dict):
    """Send a test event to the configured webhook URL."""
    from db import SessionLocal
    from models import Profile
    from services.webhooks import emit
    user_id = data.get("user_id")

    db = SessionLocal()
    try:
        user = db.query(Profile).filter(Profile.id == user_id).first()
        if not user or not user.webhook_url:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Webhook URL not configured")
    finally:
        db.close()

    emit(user_id, "webhook.test", {
        "message": "This is a test webhook event from Email Optimizer",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    return {"status": "sent", "url": user.webhook_url}


@app.get("/api/webhook-events")
async def list_webhook_events(user_id: str = None):
    """List recent webhook events."""
    from db import SessionLocal
    from models import WebhookEvent
    db = SessionLocal()
    try:
        query = db.query(WebhookEvent).order_by(WebhookEvent.created_at.desc())
        if user_id:
            query = query.filter(WebhookEvent.user_id == user_id)
        events = query.limit(50).all()
        return {
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "delivered": e.delivered,
                    "attempts": e.attempts,
                    "response_status": e.response_status,
                    "payload": e.payload,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ]
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
