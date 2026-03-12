"""
Vayne.io API client — LinkedIn Sales Navigator scraping.
"""

import os
import time
import logging
import requests

log = logging.getLogger("vayne")

BASE_URL = "https://www.vayne.io"


class VayneClient:
    def __init__(self, api_token: str):
        self.token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> dict:
        r = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict) -> dict:
        r = self.session.post(f"{BASE_URL}{path}", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    def get_credits(self) -> dict:
        """GET /api/credits — returns available credits and daily limits."""
        return self._get("/api/credits")

    def check_url(self, url: str) -> dict:
        """POST /api/url_checks — validate Sales Nav URL, return prospect count.
        Returns: {total: int, type: 'leads'|'accounts'}
        """
        return self._post("/api/url_checks", {"url": url})

    def create_order(self, url: str, name: str, limit: int = None,
                     email_enrichment: bool = False,
                     export_format: str = "simple") -> dict:
        """POST /api/orders — create a scraping order.
        Returns: {order: {id, url, name, order_type, limit, scraping_status}}
        """
        payload = {"url": url, "name": name, "export_format": export_format}
        if limit:
            payload["limit"] = limit
        if email_enrichment:
            payload["email_enrichment"] = True
        return self._post("/api/orders", payload)

    def get_order(self, order_id: int) -> dict:
        """GET /api/orders/{id} — get order status and export URLs."""
        return self._get(f"/api/orders/{order_id}")

    def generate_export(self, order_id: int, export_format: str = "simple") -> dict:
        """POST /api/orders/{id}/export — trigger CSV export generation."""
        return self._post(f"/api/orders/{order_id}/export", {"export_format": export_format})

    def wait_for_order(self, order_id: int, timeout: int = 900, poll_interval: int = 15) -> dict:
        """Poll until order scraping_status is 'finished' or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            data = self.get_order(order_id)
            order = data.get("order", data)
            status = order.get("scraping_status")
            scraped = order.get("scraped", 0)
            total = order.get("total", 0)
            log.info("Order %d: status=%s, scraped=%d/%d", order_id, status, scraped, total)

            if status == "finished":
                return data
            if status == "failed":
                raise RuntimeError(f"Vayne order {order_id} failed")

            time.sleep(poll_interval)

        raise TimeoutError(f"Vayne order {order_id} timed out after {timeout}s")

    def download_csv(self, file_url: str, output_path: str) -> str:
        """Download a CSV export from Vayne's S3 URL."""
        r = requests.get(file_url, timeout=120)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        log.info("Downloaded CSV to %s (%d bytes)", output_path, len(r.content))
        return output_path

    def list_orders(self) -> list:
        """GET /api/orders — list all non-expired orders."""
        data = self._get("/api/orders")
        return data.get("orders", [])
