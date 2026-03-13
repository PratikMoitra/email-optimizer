"""
Pipeline orchestrator — state machine that drives leads through all stages.

Stages: pending → validated → researched → generated → deployed
                                                     → skipped | error
"""

import csv
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from db import SessionLocal
from models import Batch, Lead, Profile, UserApiKey, UserOAuthToken
from services.webhooks import emit
from pipeline.vayne import VayneClient
from pipeline.anymailfinder import AnymailfinderClient
from pipeline.researcher import research_company
from pipeline.email_gen import generate_sequences, load_cold_email_rules
from pipeline.instantly import InstantlyClient

log = logging.getLogger("orchestrator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decrypt_key(encrypted: str) -> str:
    """Decrypt a user API key. For staging, keys are stored in plain text."""
    # TODO: implement AES-256 decryption with settings.ENCRYPTION_KEY
    return encrypted


def _get_user_key(db, user_id: str, service: str) -> str:
    """Get a decrypted API key for a user + service."""
    key_row = db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id,
        UserApiKey.service == service,
    ).first()
    if not key_row:
        raise ValueError(f"No API key configured for service '{service}'")
    return _decrypt_key(key_row.encrypted_key)


# ---------------------------------------------------------------------------
# Stage 1: SCRAPE
# ---------------------------------------------------------------------------

def stage_scrape(batch_id: int):
    """Create Vayne order, wait for completion, download CSV, insert leads."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        vayne_token = _get_user_key(db, batch.user_id, "vayne")
        vayne = VayneClient(vayne_token)

        # Check credits
        credits = vayne.get_credits()
        available = credits.get("credit_available", 0)
        log.info("Vayne credits available: %d", available)

        if available <= 0:
            log.warning("No Vayne credits available, skipping scrape")
            emit(batch.user_id, "credits.low", {"service": "vayne", "remaining": 0}, batch_id)
            return

        # Create order
        log.info("Creating Vayne order for batch '%s'", batch.name)
        order_data = vayne.create_order(
            url=batch.sales_nav_url,
            name=batch.name,
        )
        order = order_data.get("order", order_data)
        batch.vayne_order_id = order.get("id")
        batch.total_leads = order.get("total", 0)
        db.commit()

        emit(batch.user_id, "batch.created", {
            "batch_id": batch.id,
            "name": batch.name,
            "total_leads": batch.total_leads,
            "sales_nav_url": batch.sales_nav_url,
        }, batch_id)

        # Wait for scraping to finish
        vayne.wait_for_order(batch.vayne_order_id)

        # Generate and download export
        vayne.generate_export(batch.vayne_order_id, export_format="simple")

        # Poll until export is ready
        import time
        for _ in range(60):
            order_data = vayne.get_order(batch.vayne_order_id)
            order = order_data.get("order", order_data)
            exports = order.get("exports", {})
            simple = exports.get("simple", {})
            if simple.get("status") == "completed" and simple.get("file_url"):
                break
            time.sleep(5)

        file_url = simple.get("file_url")
        if not file_url:
            raise RuntimeError("Export file URL not available")

        # Download CSV
        csv_path = tempfile.mktemp(suffix=".csv")
        vayne.download_csv(file_url, csv_path)

        # Parse and insert leads
        _import_csv(db, batch, csv_path)

        batch.status = "validating"
        db.commit()

        emit(batch.user_id, "batch.scrape_complete", {
            "batch_id": batch.id,
            "total_leads": batch.total_leads,
        }, batch_id)

    finally:
        db.close()


def _import_csv(db, batch: Batch, csv_path: str):
    """Parse Vayne CSV and insert leads into database."""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            lead = Lead(
                batch_id=batch.id,
                original_first_name=row.get("firstName", row.get("first_name", "")),
                original_last_name=row.get("lastName", row.get("last_name", "")),
                company_name=row.get("companyName", row.get("company_name", "")),
                company_domain=row.get("companyDomain", row.get("company_domain", "")),
                job_title=row.get("title", row.get("job_title", "")),
                industry=row.get("industry", ""),
                linkedin_url=row.get("linkedinUrl", row.get("linkedin_url", "")),
                stage="pending",
            )
            db.add(lead)
            count += 1

        db.flush()
        batch.total_leads = count
        log.info("Imported %d leads from CSV for batch %d", count, batch.id)


def import_from_csv(batch_id: int, csv_path: str):
    """Import leads from an existing CSV file (skip Vayne scraping)."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        _import_csv(db, batch, csv_path)
        batch.status = "validating"
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stage 2: VALIDATE
# ---------------------------------------------------------------------------

def stage_validate(batch_id: int):
    """Validate pending leads via Anymailfinder. Credit-aware batching."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            return

        amf_key = _get_user_key(db, batch.user_id, "anymailfinder")
        amf = AnymailfinderClient(amf_key)

        # Get pending leads
        pending = db.query(Lead).filter(
            Lead.batch_id == batch_id,
            Lead.stage == "pending",
        ).all()

        if not pending:
            log.info("No pending leads for batch %d, moving to research", batch_id)
            batch.status = "researching"
            db.commit()
            return

        validated_count = 0
        valid_count = 0

        for lead in pending:
            domain = lead.company_domain
            if not domain and lead.email:
                domain = lead.email.split("@")[-1]

            try:
                result = amf.find_decision_maker(
                    domain=domain,
                    company_name=lead.company_name,
                    categories=["ceo", "sales", "marketing"],
                )

                lead.email_status = result.get("email_status", "not_found")

                if lead.email_status == "valid":
                    lead.email = result.get("valid_email") or result.get("email")
                    full_name = result.get("person_full_name", "")
                    first, last = AnymailfinderClient.parse_name(full_name)
                    lead.first_name = first
                    lead.last_name = last
                    lead.job_title = result.get("person_job_title", lead.job_title)
                    lead.stage = "validated"
                    valid_count += 1
                else:
                    lead.stage = "skipped"

                lead.stage_updated_at = datetime.utcnow()
                validated_count += 1

            except Exception as e:
                lead.stage = "error"
                lead.error_message = str(e)[:500]
                log.error("AMF error for lead %d: %s", lead.id, e)

            db.commit()

        batch.leads_validated += validated_count
        batch.leads_valid += valid_count
        batch.credits_used += valid_count * 2  # 2 credits per valid email

        # Check if all leads processed
        remaining = db.query(Lead).filter(
            Lead.batch_id == batch_id, Lead.stage == "pending"
        ).count()

        if remaining == 0:
            batch.status = "researching"

        db.commit()

        emit(batch.user_id, "batch.validation_progress", {
            "batch_id": batch.id,
            "validated_today": validated_count,
            "valid": valid_count,
            "remaining": remaining,
        }, batch_id)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stage 3: RESEARCH
# ---------------------------------------------------------------------------

def stage_research(batch_id: int):
    """Research validated leads — scrape company websites + GPT-4o analysis."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            return

        openai_key = _get_user_key(db, batch.user_id, "openai")

        validated = db.query(Lead).filter(
            Lead.batch_id == batch_id,
            Lead.stage == "validated",
        ).all()

        if not validated:
            batch.status = "generating"
            db.commit()
            return

        for lead in validated:
            try:
                result = research_company(
                    domain=lead.company_domain or "",
                    company_name=lead.company_name or "",
                    industry=lead.industry or "",
                    first_name=lead.first_name or "",
                    last_name=lead.last_name or "",
                    job_title=lead.job_title or "",
                    openai_api_key=openai_key,
                )
                lead.company_summary = result.get("company_summary", "")
                lead.niche_pain_points = json.dumps(result.get("sales_pain_points", []))
                lead.stage = "researched"
                lead.stage_updated_at = datetime.utcnow()
                batch.leads_researched += 1

            except Exception as e:
                lead.stage = "error"
                lead.error_message = f"Research failed: {str(e)[:400]}"
                log.error("Research error for lead %d: %s", lead.id, e)

            db.commit()

        # Check if all validated leads are researched
        remaining = db.query(Lead).filter(
            Lead.batch_id == batch_id, Lead.stage == "validated"
        ).count()

        if remaining == 0:
            batch.status = "generating"

        db.commit()

        emit(batch.user_id, "batch.research_progress", {
            "batch_id": batch.id,
            "researched_today": len(validated),
            "remaining": remaining,
        }, batch_id)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stage 4: GENERATE
# ---------------------------------------------------------------------------

def stage_generate(batch_id: int):
    """Generate email sequences for researched leads, grouped by industry."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            return

        openai_key = _get_user_key(db, batch.user_id, "openai")
        cold_email_rules = load_cold_email_rules()

        researched = db.query(Lead).filter(
            Lead.batch_id == batch_id,
            Lead.stage == "researched",
        ).all()

        if not researched:
            batch.status = "deploying"
            db.commit()
            return

        # Group by industry for efficiency (one GPT call per industry group)
        from collections import defaultdict
        by_industry = defaultdict(list)
        for lead in researched:
            by_industry[lead.industry or "general"].append(lead)

        for industry, leads in by_industry.items():
            # Use first lead's research as representative for the industry group
            representative = leads[0]
            pain_points = json.loads(representative.niche_pain_points or "[]")

            try:
                sequences = generate_sequences(
                    industry=industry,
                    job_titles=list(set(l.job_title for l in leads if l.job_title)),
                    company_summary=representative.company_summary or "",
                    niche=industry,
                    pain_points=pain_points,
                    undeniable_offer="",
                    cold_email_rules=cold_email_rules,
                    openai_api_key=openai_key,
                )

                for lead in leads:
                    lead.email_sequences = sequences
                    lead.stage = "generated"
                    lead.stage_updated_at = datetime.utcnow()
                    batch.leads_generated += 1

            except Exception as e:
                log.error("Email gen error for industry '%s': %s", industry, e)
                for lead in leads:
                    lead.stage = "error"
                    lead.error_message = f"Email gen failed: {str(e)[:400]}"

            db.commit()

        batch.status = "deploying"
        db.commit()

        emit(batch.user_id, "batch.emails_generated", {
            "batch_id": batch.id,
            "generated_count": batch.leads_generated,
        }, batch_id)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stage 5: DEPLOY
# ---------------------------------------------------------------------------

def stage_deploy(batch_id: int):
    """Deploy generated leads to Instantly campaign + Google Sheets."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            return

        instantly_key = _get_user_key(db, batch.user_id, "instantly")
        instantly = InstantlyClient(instantly_key)

        generated = db.query(Lead).filter(
            Lead.batch_id == batch_id,
            Lead.stage == "generated",
        ).all()

        if not generated:
            batch.status = "complete"
            db.commit()
            return

        # Ensure campaign exists
        if not batch.instantly_campaign_id:
            # Build sequences from first lead
            sample = generated[0]
            seqs = sample.email_sequences or {}
            instantly_sequences = _build_instantly_sequences(seqs)

            schedule = {
                "name": "Default",
                "days": {"1": True, "2": True, "3": True, "4": True, "5": True, "6": True, "7": True},
                "startHour": "09:00",
                "endHour": "17:00",
                "timezone": "America/Chicago",
            }

            campaign = instantly.create_campaign(
                name=batch.name,
                sequences=instantly_sequences,
                schedule=schedule,
            )
            batch.instantly_campaign_id = campaign.get("id")
            db.commit()
            log.info("Created Instantly campaign %s for batch '%s'", batch.instantly_campaign_id, batch.name)

        # Add leads to campaign
        lead_data = [
            {
                "email": lead.email,
                "first_name": lead.first_name or "",
                "last_name": lead.last_name or "",
                "company_name": lead.company_name or "",
            }
            for lead in generated
            if lead.email
        ]

        if lead_data:
            instantly.add_leads(batch.instantly_campaign_id, lead_data)

            # Activate campaign
            instantly.activate_campaign(batch.instantly_campaign_id)

        for lead in generated:
            lead.stage = "deployed"
            lead.stage_updated_at = datetime.utcnow()
            batch.leads_deployed += 1

        # Check if batch is complete
        remaining_stages = db.query(Lead).filter(
            Lead.batch_id == batch_id,
            Lead.stage.in_(["pending", "validated", "researched", "generated"]),
        ).count()

        if remaining_stages == 0:
            batch.status = "complete"

        db.commit()

        emit(batch.user_id, "batch.deployed", {
            "batch_id": batch.id,
            "campaign_id": batch.instantly_campaign_id,
            "leads_added": len(lead_data),
        }, batch_id)

        if batch.status == "complete":
            emit(batch.user_id, "batch.complete", {
                "batch_id": batch.id,
                "summary": {
                    "total": batch.total_leads,
                    "valid": batch.leads_valid,
                    "deployed": batch.leads_deployed,
                    "skipped": batch.total_leads - batch.leads_valid,
                },
            }, batch_id)

            # Sync to Google Sheets if connected
            _sync_to_sheets(db, batch, generated)

    finally:
        db.close()


def _build_instantly_sequences(email_data: dict) -> list:
    """Convert GPT-4o sequence JSON to Instantly's sequence format."""
    sequences = email_data.get("sequences", [])
    if not sequences:
        return []

    # Use variant_a as default for Instantly
    result = []
    for seq in sequences:
        step = {
            "steps": [{
                "type": "email",
                "subject": seq.get("variant_a", {}).get("subject", ""),
                "body": seq.get("variant_a", {}).get("body", ""),
                "delay": seq.get("day", 0),
            }]
        }
        result.append(step)

    return result


def _sync_to_sheets(db, batch: Batch, leads: list):
    """Sync deployed leads to Google Sheets if user has connected Google."""
    try:
        google_token = db.query(UserOAuthToken).filter(
            UserOAuthToken.user_id == batch.user_id,
            UserOAuthToken.provider == "google",
        ).first()

        if not google_token:
            log.info("Google Sheets not connected for user %s — skipping sync", batch.user_id)
            return

        sheet_id = (google_token.provider_metadata or {}).get("sheet_id")
        if not sheet_id:
            log.info("No Google Sheet selected for user %s — skipping sync", batch.user_id)
            return

        from security.encryption import decrypt
        from services.sheets import get_client_from_oauth_token, sync_leads

        access_token = decrypt(google_token.access_token)
        refresh_token = decrypt(google_token.refresh_token) if google_token.refresh_token else None

        client, updated = get_client_from_oauth_token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=google_token.token_expires_at,
        )

        # If token was refreshed, save it
        if updated:
            from security.encryption import encrypt
            google_token.access_token = encrypt(updated["access_token"])
            if updated.get("token_expires_at"):
                google_token.token_expires_at = updated["token_expires_at"]
            db.commit()

        lead_dicts = [
            {
                "first_name": l.first_name or "",
                "last_name": l.last_name or "",
                "email": l.email or "",
                "email_status": l.email_status or "",
                "company_name": l.company_name or "",
                "company_domain": l.company_domain or "",
                "job_title": l.job_title or "",
                "industry": l.industry or "",
                "linkedin_url": l.linkedin_url or "",
                "company_summary": l.company_summary or "",
                "niche_pain_points": l.niche_pain_points or "",
                "stage": l.stage or "",
            }
            for l in leads
        ]

        sync_leads(client, sheet_id, lead_dicts, batch.name)
        log.info("Synced %d leads to Google Sheets for batch '%s'", len(lead_dicts), batch.name)

    except Exception as e:
        log.error("Google Sheets sync failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# Main resume function (called by scheduler)
# ---------------------------------------------------------------------------

STAGE_MAP = {
    "scraping": stage_scrape,
    "validating": stage_validate,
    "researching": stage_research,
    "generating": stage_generate,
    "deploying": stage_deploy,
}


def resume_batch(batch_id: int):
    """Resume a batch from its current stage."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch or batch.status in ("complete", "paused"):
            return

        stage_fn = STAGE_MAP.get(batch.status)
        if stage_fn:
            log.info("Running stage '%s' for batch %d", batch.status, batch_id)
            stage_fn(batch_id)
        else:
            log.warning("Unknown batch status '%s' for batch %d", batch.status, batch_id)
    finally:
        db.close()
