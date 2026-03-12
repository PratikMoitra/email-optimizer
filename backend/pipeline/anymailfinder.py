"""
Anymailfinder API client — email finding and validation.
"""

import logging
import requests

log = logging.getLogger("anymailfinder")

BASE_URL = "https://api.anymailfinder.com/v5.1"


class AnymailfinderClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key,
            "Content-Type": "application/json",
        })

    def find_decision_maker(
        self,
        domain: str = None,
        company_name: str = None,
        categories: list[str] = None,
    ) -> dict:
        """
        POST /find-email/decision-maker — find and validate a decision maker's email.

        Args:
            domain: Company domain (preferred, more accurate)
            company_name: Company name (fallback)
            categories: Decision maker categories. Options:
                ceo, engineering, finance, hr, it, logistics,
                marketing, operations, buyer, sales

        Returns:
            {
                decision_maker_category: str,
                email: str | None,
                email_status: 'valid' | 'risky' | 'not_found' | 'blacklisted',
                person_full_name: str,
                person_job_title: str,
                person_linkedin_url: str,
                valid_email: str | None
            }

        Pricing: 2 credits per valid email found. Free for risky/not_found/blacklisted.
        Timeout: API recommends 180s — searches are real-time.
        """
        if not domain and not company_name:
            raise ValueError("Either domain or company_name must be provided")

        if categories is None:
            categories = ["ceo"]

        payload = {"decision_maker_category": categories}
        if domain:
            payload["domain"] = domain
        if company_name:
            payload["company_name"] = company_name

        try:
            r = self.session.post(
                f"{BASE_URL}/find-email/decision-maker",
                json=payload,
                timeout=180,
            )
            r.raise_for_status()
            result = r.json()

            log.info(
                "AMF result for %s: status=%s, email=%s, person=%s",
                domain or company_name,
                result.get("email_status"),
                result.get("email", "N/A"),
                result.get("person_full_name", "N/A"),
            )
            return result

        except requests.RequestException as e:
            log.error("AMF request failed for %s: %s", domain or company_name, e)
            raise

    @staticmethod
    def parse_name(full_name: str) -> tuple[str, str]:
        """Split 'FirstName LastName' into (first, last)."""
        if not full_name:
            return ("", "")
        parts = full_name.strip().split(None, 1)
        first = parts[0] if parts else ""
        last = parts[1] if len(parts) > 1 else ""
        return (first, last)
