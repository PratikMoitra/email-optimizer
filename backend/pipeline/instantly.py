"""
Instantly.ai API v2 client — campaign management and lead deployment.
Extended with tag-based account filtering for inboxly-tagged accounts.
"""

import os
import time
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger("instantly")

BASE_URL = "https://api.instantly.ai/api/v2"
BULK_BATCH_SIZE = 1000


class InstantlyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None, retries: int = 3) -> dict:
        for attempt in range(retries):
            r = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
            if r.status_code == 429:
                log.warning("Rate limited GET %s, waiting 30s (attempt %d)", path, attempt + 1)
                time.sleep(30)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"GET {path} failed after {retries} retries (429)")

    def _post(self, path: str, payload: dict, retries: int = 3) -> dict:
        for attempt in range(retries):
            r = self.session.post(f"{BASE_URL}{path}", json=payload, timeout=60)
            if r.status_code == 429:
                log.warning("Rate limited POST %s, waiting 30s (attempt %d)", path, attempt + 1)
                time.sleep(30)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"POST {path} failed after {retries} retries (429)")

    # --- Tags ---

    def get_tag_id(self, tag_name: str) -> str | None:
        """Find tag ID by name from custom tags."""
        data = self._get("/custom-tags", params={"limit": 100})
        tags = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(tags, list):
            for tag in tags:
                if tag.get("name", "").lower() == tag_name.lower():
                    return tag.get("id")
        return None

    # --- Accounts ---

    def get_sending_accounts_by_tag(self, tag_name: str) -> list[str]:
        """Get active sending account emails filtered by tag name (e.g., 'inboxly')."""
        tag_id = self.get_tag_id(tag_name)
        if not tag_id:
            log.warning("Tag '%s' not found, falling back to all active accounts", tag_name)
            return self.get_active_sending_accounts()

        all_emails = []
        starting_after = None
        while True:
            params = {"limit": 100, "tag_ids": tag_id}
            if starting_after:
                params["starting_after"] = starting_after
            data = self._get("/accounts", params=params)
            items = data.get("items", [])
            all_emails.extend(a["email"] for a in items if a.get("status") == 1)
            starting_after = data.get("next_starting_after")
            if not starting_after or not items:
                break

        log.info("Found %d inboxly-tagged active accounts", len(all_emails))
        return all_emails

    def get_active_sending_accounts(self) -> list[str]:
        """Get all active sending account emails (fallback)."""
        all_emails = []
        starting_after = None
        while True:
            params = {"limit": 100}
            if starting_after:
                params["starting_after"] = starting_after
            data = self._get("/accounts", params=params)
            items = data.get("items", [])
            all_emails.extend(a["email"] for a in items if a.get("status") == 1)
            starting_after = data.get("next_starting_after")
            if not starting_after or not items:
                break
        return all_emails

    # --- Campaigns ---

    def create_campaign(self, name: str, sequences: list, schedule: dict,
                        daily_limit: int = 50, email_gap: int = 10,
                        tag_name: str = "inboxly") -> dict:
        """Create a campaign with inboxly-tagged sending accounts."""
        start = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        email_list = self.get_sending_accounts_by_tag(tag_name)
        if not email_list:
            raise RuntimeError(f"No active sending accounts with tag '{tag_name}'")

        payload = {
            "name": name,
            "sequences": sequences,
            "campaign_schedule": {
                "start_date": start,
                "end_date": end,
                "schedules": [schedule],
            },
            "email_gap": email_gap,
            "daily_limit": daily_limit,
            "email_list": email_list,
            "stop_on_reply": True,
            "stop_on_auto_reply": True,
            "link_tracking": False,
            "open_tracking": False,
            "text_only": True,
        }
        result = self._post("/campaigns", payload)
        log.info("Created campaign '%s' with %d sending accounts", name, len(email_list))
        return result

    def activate_campaign(self, campaign_id: str) -> dict:
        return self._post(f"/campaigns/{campaign_id}/activate", {"status": 1})

    def get_campaign(self, campaign_id: str) -> dict:
        return self._get(f"/campaigns/{campaign_id}")

    def get_analytics(self, campaign_id: str) -> dict:
        result = self._get("/campaigns/analytics", params={"id": campaign_id})
        if isinstance(result, list):
            return result[0] if result else {}
        return result

    # --- Leads ---

    def add_leads(self, campaign_id: str, leads: list[dict]) -> int:
        """Bulk add leads to campaign. Batches at 1000 per request.
        Each lead dict should have: email, first_name, last_name, company_name
        """
        total_added = 0
        for i in range(0, len(leads), BULK_BATCH_SIZE):
            batch = leads[i:i + BULK_BATCH_SIZE]
            lead_objects = []
            for lead in batch:
                obj = {"email": lead["email"]}
                if lead.get("first_name"):
                    obj["first_name"] = lead["first_name"]
                if lead.get("last_name"):
                    obj["last_name"] = lead["last_name"]
                if lead.get("company_name"):
                    obj["company_name"] = lead["company_name"]
                lead_objects.append(obj)

            payload = {
                "campaign_id": campaign_id,
                "leads": lead_objects,
                "skip_if_in_workspace": False,
            }
            result = self._post("/leads/add", payload)
            added = result.get("upload_count", len(batch))
            total_added += added
            log.info("Bulk upload batch %d-%d: %d added", i + 1, i + len(batch), added)

        log.info("Added %d/%d leads to campaign %s", total_added, len(leads), campaign_id)
        return total_added
