"""
Google Sheets sync — updates a shared sheet with pipeline lead data.

Supports two authentication modes:
  1. User OAuth tokens (multi-tenant: each user signs in with their Google account)
  2. Service Account fallback (for backward compatibility / CI)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request

from config import settings

log = logging.getLogger("sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADER_ROW = [
    "First Name", "Last Name", "Email", "Email Status",
    "Company", "Domain", "Job Title", "Industry",
    "LinkedIn", "Company Summary", "Pain Points",
    "Stage", "Batch",
]


def get_client_from_oauth_token(
    access_token: str,
    refresh_token: str | None = None,
    token_expiry: datetime | None = None,
) -> tuple[gspread.Client, dict]:
    """
    Authenticate with Google Sheets using a user's OAuth2 token.

    Returns (gspread_client, updated_token_info).
    updated_token_info contains refreshed access_token + expiry if token was refreshed.
    """
    creds = OAuthCredentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )

    # Set expiry if available
    if token_expiry:
        creds.expiry = token_expiry.replace(tzinfo=None)  # google-auth expects naive UTC

    # Refresh if expired
    updated_token_info = {}
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        updated_token_info = {
            "access_token": creds.token,
            "token_expires_at": creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None,
        }
        log.info("Google OAuth token refreshed")

    return gspread.authorize(creds), updated_token_info


def list_spreadsheets(client: gspread.Client) -> list[dict]:
    """List all spreadsheets accessible to the authenticated user."""
    sheets = client.openall()
    return [
        {"id": s.id, "title": s.title, "url": s.url}
        for s in sheets
    ]


def sync_leads(client: gspread.Client, sheet_id: str, leads: list, batch_name: str):
    """
    Upsert leads into the Google Sheet.
    Creates header row if sheet is empty.
    """
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.sheet1

    # Ensure header row
    existing = worksheet.get_all_values()
    if not existing:
        worksheet.append_row(HEADER_ROW)

    # Build rows
    rows = []
    for lead in leads:
        pain_points = lead.get("niche_pain_points", "")
        if isinstance(pain_points, list):
            pain_points = "; ".join(pain_points)

        rows.append([
            lead.get("first_name", ""),
            lead.get("last_name", ""),
            lead.get("email", ""),
            lead.get("email_status", ""),
            lead.get("company_name", ""),
            lead.get("company_domain", ""),
            lead.get("job_title", ""),
            lead.get("industry", ""),
            lead.get("linkedin_url", ""),
            lead.get("company_summary", ""),
            pain_points,
            lead.get("stage", ""),
            batch_name,
        ])

    if rows:
        worksheet.append_rows(rows)
        log.info("Synced %d leads to Google Sheet", len(rows))
