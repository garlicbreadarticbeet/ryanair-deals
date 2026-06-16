"""Dunne Mollie-REST-client (requests + certifi). Mockbaar in tests (monkeypatch deze functies).

Alleen wat we nodig hebben voor abonnementen: customer + first payment (mandaat) + subscription.
"""
from __future__ import annotations

from app.net import get_session
from app.settings import settings

_BASE = "https://api.mollie.com/v2"


class MollieError(Exception):
    """Mollie gaf een fout of is niet geconfigureerd."""


def _headers() -> dict:
    if not settings.mollie_api_key:
        raise MollieError("MOLLIE_API_KEY niet ingesteld")
    return {"Authorization": f"Bearer {settings.mollie_api_key}"}


def _post(path: str, payload: dict) -> dict:
    resp = get_session().post(f"{_BASE}{path}", headers=_headers(), json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        raise MollieError(f"Mollie POST {path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _get(path: str) -> dict:
    resp = get_session().get(f"{_BASE}{path}", headers=_headers(), timeout=20)
    if resp.status_code != 200:
        raise MollieError(f"Mollie GET {path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def create_customer(email: str | None = None, name: str | None = None) -> dict:
    payload = {k: v for k, v in {"email": email, "name": name}.items() if v}
    return _post("/customers", payload)


def create_first_payment(
    *, customer_id: str, amount: str, currency: str, description: str,
    redirect_url: str, webhook_url: str,
) -> dict:
    """Eerste betaling (sequenceType=first) om een mandaat op te zetten; bevat checkout-URL."""
    return _post(
        "/payments",
        {
            "amount": {"currency": currency, "value": amount},
            "description": description,
            "redirectUrl": redirect_url,
            "webhookUrl": webhook_url,
            "customerId": customer_id,
            "sequenceType": "first",
        },
    )


def get_payment(payment_id: str) -> dict:
    return _get(f"/payments/{payment_id}")


def create_subscription(
    *, customer_id: str, amount: str, currency: str, interval: str,
    description: str, webhook_url: str,
) -> dict:
    return _post(
        f"/customers/{customer_id}/subscriptions",
        {
            "amount": {"currency": currency, "value": amount},
            "interval": interval,
            "description": description,
            "webhookUrl": webhook_url,
        },
    )


def cancel_subscription(customer_id: str, subscription_id: str) -> dict:
    resp = get_session().delete(
        f"{_BASE}/customers/{customer_id}/subscriptions/{subscription_id}",
        headers=_headers(), timeout=20,
    )
    if resp.status_code not in (200, 204):
        raise MollieError(f"Mollie cancel -> {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}
