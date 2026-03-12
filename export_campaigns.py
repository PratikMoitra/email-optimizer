"""
export_campaigns.py — Export all Instantly campaigns (copy, settings, analytics) to local archive.

Saves each campaign as a JSON file + a combined summary CSV.

Usage:
  python export_campaigns.py
"""

import os
import csv
import json
import logging
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("export")

BASE_URL = "https://api.instantly.ai/api/v2"
ROOT = Path(__file__).parent
ARCHIVE_DIR = ROOT / "data" / "campaign-archive"


def headers():
    return {
        "Authorization": f"Bearer {os.environ['INSTANTLY_API_KEY']}",
        "Content-Type": "application/json",
    }


def get_all_campaigns():
    all_campaigns = []
    starting_after = None
    while True:
        params = {"limit": 100}
        if starting_after:
            params["starting_after"] = starting_after
        r = requests.get(f"{BASE_URL}/campaigns", headers=headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
        all_campaigns.extend(items)
        starting_after = data.get("next_starting_after")
        if not starting_after or not items:
            break
    return all_campaigns


def get_campaign_detail(campaign_id):
    """GET /api/v2/campaigns/{id} — full campaign with sequences."""
    r = requests.get(f"{BASE_URL}/campaigns/{campaign_id}", headers=headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def get_campaign_analytics(campaign_id):
    """GET /api/v2/campaigns/analytics?id={id}"""
    r = requests.get(f"{BASE_URL}/campaigns/analytics", headers=headers(),
                     params={"id": campaign_id}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data[0] if data else {}
    return data


STATUS_MAP = {0: "Draft", 1: "Active", 2: "Paused", 3: "Completed",
              4: "Running Subsequences", -1: "Accounts Unhealthy",
              -2: "Bounce Protect", -99: "Account Suspended"}


def main():
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    campaigns = get_all_campaigns()
    log.info("Found %d campaigns. Exporting...", len(campaigns))

    summary_rows = []

    for i, c in enumerate(campaigns):
        cid = c["id"]
        name = c.get("name", "unnamed")
        status = c.get("status", 0)
        log.info("[%d/%d] %s (status=%s)", i + 1, len(campaigns), name, STATUS_MAP.get(status, status))

        # Get full detail (includes sequences with copy)
        try:
            detail = get_campaign_detail(cid)
        except Exception as e:
            log.warning("  Failed to get detail: %s", e)
            detail = c

        # Get analytics
        try:
            analytics = get_campaign_analytics(cid)
        except Exception as e:
            log.warning("  Failed to get analytics: %s", e)
            analytics = {}

        # Combine into archive record
        record = {
            "campaign": detail,
            "analytics": analytics,
        }

        # Save individual JSON
        safe_name = "".join(ch if ch.isalnum() or ch in "- _" else "_" for ch in name)[:60]
        filename = ARCHIVE_DIR / f"{safe_name}_{cid[:8]}.json"
        with open(filename, "w") as f:
            json.dump(record, f, indent=2, default=str)

        # Extract email copy from sequences
        sequences = detail.get("sequences", [])
        email_copy = []
        for seq in sequences:
            for step in seq.get("steps", []):
                for variant in step.get("variants", []):
                    subject = variant.get("subject", "")
                    body = variant.get("body", "")
                    email_copy.append(f"Subject: {subject}\n{body}")

        # Summary row
        summary_rows.append({
            "name": name,
            "id": cid,
            "status": STATUS_MAP.get(status, str(status)),
            "created": detail.get("timestamp_created", ""),
            "daily_limit": detail.get("daily_limit", ""),
            "emails_sent": analytics.get("emails_sent_count", 0),
            "leads_contacted": analytics.get("leads_contacted_count", 0),
            "opens": analytics.get("open_count", 0),
            "replies": analytics.get("reply_count", 0),
            "bounces": analytics.get("bounce_count", 0),
            "unsubscribes": analytics.get("unsubscribe_count", 0),
            "reply_rate": f"{analytics.get('reply_count', 0) / max(analytics.get('emails_sent_count', 1), 1):.2%}",
            "email_copy": "\n---\n".join(email_copy) if email_copy else "",
        })

    # Write summary CSV
    summary_file = ARCHIVE_DIR / "campaign_summary.csv"
    fieldnames = ["name", "id", "status", "created", "daily_limit",
                  "emails_sent", "leads_contacted", "opens", "replies",
                  "bounces", "unsubscribes", "reply_rate", "email_copy"]
    with open(summary_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    log.info("=" * 50)
    log.info("Exported %d campaigns to %s", len(campaigns), ARCHIVE_DIR)
    log.info("Summary CSV: %s", summary_file)

    # Print quick stats
    total_sent = sum(r.get("emails_sent", 0) or 0 for r in summary_rows)
    total_replies = sum(r.get("replies", 0) or 0 for r in summary_rows)
    log.info("Total emails sent across all campaigns: %d", total_sent)
    log.info("Total replies: %d (%.2f%% overall)", total_replies,
             (total_replies / max(total_sent, 1)) * 100)


if __name__ == "__main__":
    main()
