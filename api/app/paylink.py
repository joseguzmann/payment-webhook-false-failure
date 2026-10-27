"""Client for the PayLink gateway: creates payment links. Results arrive later through the webhook."""

import httpx

from . import config


class PayLinkClient:
    def __init__(self, base_url: str = config.GATEWAY_URL, callback_url: str = config.CALLBACK_URL):
        self.base_url = base_url
        self.callback_url = callback_url

    def create_link(self, reference: str, amount_cents: int) -> dict:
        response = httpx.post(
            f"{self.base_url}/links",
            json={"reference": reference, "amount_cents": amount_cents, "callback_url": self.callback_url},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
