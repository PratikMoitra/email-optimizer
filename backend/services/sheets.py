"""
Google Sheets sync — updates a shared sheet with pipeline lead data.
"""

import logging
import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger("sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADER_ROW = [
    "First Name", "Last Name", "Email", "Email Status",
    "Company", "Domain", "Job Title", "Industry",
    "LinkedIn", "Company Summary", "Pain Points",
    "Stage", "Batch",
]


def get_client(creds_file: str) -> gspread.Client:
    """Authenticate with Google Sheets using a service account."""
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    return gspread.authorize(creds)


def sync_leads(creds_file: str, sheet_id: str, leads: list, batch_name: str):
    """
    Upsert leads into the Google Sheet.
    Creates header row if sheet is empty.
    """
    client = get_client(creds_file)
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
