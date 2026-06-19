"""Dunne Lemon Squeezy-REST-client (requests + certifi via app/net.py). Mockbaar in tests.

Lemon Squeezy is Merchant of Record: zij zijn de verkoper en regelen de EU-btw, dus we kunnen
innen zonder eigen KvK. JSON:API (``application/vnd.api+json``). Alleen wat we nodig hebben:
een checkout aanmaken voor een variant (maand/jaar) met vooringevulde e-mail + ``custom_data``
zodat de webhook de gebruiker terugvindt, en een abonnement opzeggen. De
webhook-signatuurverificatie (HMAC-SHA256 over de rauwe body) staat hier ook.
"""
from __future__ import annotations

import hashlib
import hmac

from app.net import get_session
from app.settings import settings

_BASE = "https://api.lemonsqueezy.com/v1"
_MEDIA = "application/vnd.api+json"


class LemonSqueezyError(Exception):
    """Lemon Squeezy gaf een fout of is niet geconfigureerd."""


def _headers() -> dict:
    if not settings.lemonsqueezy_api_key:
        raise LemonSqueezyError("LEMONSQUEEZY_API_KEY niet ingesteld")
    return {
        "Accept": _MEDIA,
        "Content-Type": _MEDIA,
        "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
    }


def create_checkout(
    *, store_id: str, variant_id: str, email: str | None, user_id: int, redirect_url: str
) -> str:
    """Maak een checkout voor ``variant_id`` in ``store_id``; geef de hosted checkout-URL terug.

    ``custom_data.user_id`` komt in de webhook terug als ``meta.custom_data.user_id`` zodat we
    de betaling aan de juiste gebruiker kunnen koppelen.
    """
    if not (store_id and variant_id):
        raise LemonSqueezyError("Lemon Squeezy store_id/variant_id niet ingesteld")
    checkout_data: dict = {"custom": {"user_id": str(user_id)}}
    if email:
        checkout_data["email"] = email
    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": checkout_data,
                "product_options": {"redirect_url": redirect_url},
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(store_id)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }
    resp = get_session().post(f"{_BASE}/checkouts", headers=_headers(), json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        raise LemonSqueezyError(f"Lemon Squeezy checkout -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()["data"]["attributes"]["url"]


def cancel_subscription(subscription_id: str) -> dict:
    """Zeg het abonnement op (DELETE). Lemon Squeezy laat het lopen tot einde periode (ends_at)."""
    resp = get_session().delete(
        f"{_BASE}/subscriptions/{subscription_id}", headers=_headers(), timeout=20
    )
    if resp.status_code not in (200, 204):
        raise LemonSqueezyError(f"Lemon Squeezy cancel -> {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verifieer de ``X-Signature``-header: HMAC-SHA256 (hex) over de rauwe body, constant-time.

    Vergelijk als *bytes*: ``hmac.compare_digest`` gooit een TypeError op str-args met non-ASCII
    tekens, dus een handtekening met rare bytes mag niet crashen maar gewoon ``False`` geven.
    """
    secret = settings.lemonsqueezy_webhook_secret
    if not (secret and signature):
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(digest.encode("ascii"), signature.encode("utf-8"))
    except (UnicodeEncodeError, ValueError):
        return False
