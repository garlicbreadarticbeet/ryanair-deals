"""EmailNotifier — transactionele e-mail via de Resend-API (requests + certifi).

Levert zowel de deal-alerts als (via send_email) de magic-link-mail voor onboarding.
"""
from __future__ import annotations

import html

from app.channels.base import AlertItem, register_notifier
from app.net import get_session
from app.settings import settings

_RESEND_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Verstuur één transactionele e-mail via Resend. False als niet geconfigureerd/fout."""
    if not settings.resend_api_key:
        return False
    try:
        resp = get_session().post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.resend_from, "to": [to], "subject": subject, "html": html_body},
            timeout=20,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def _render(items: list[AlertItem]) -> tuple[str, str]:
    subject = f"✈️ {len(items)} nieuwe retour-deal(s)"
    rows = []
    for it in sorted(items, key=lambda x: x.deal.total):
        d = it.deal
        drop = f" <small>(was €{it.previous_price:.2f})</small>" if it.previous_price else ""
        airline = f" · {html.escape(d.airline)}" if d.airline else ""
        link = (f' · <a href="{html.escape(d.deeplink, quote=True)}">Bekijk</a>'
                if d.deeplink else "")
        rows.append(
            f"<li><b>€{d.total:.2f}</b>{drop} — {html.escape(d.origin)} ⇄ "
            f"{html.escape(d.destination)} · {d.nights} dagen · "
            f"heen {d.out_date:%d-%m} / terug {d.in_date:%d-%m}{airline}{link}</li>"
        )
    body = (f"<h2>{subject}</h2><ul>{''.join(rows)}</ul>"
            "<p><small>Prijzen kunnen wijzigen; je boekt bij de airline.</small></p>")
    return subject, body


@register_notifier
class EmailNotifier:
    channel_type = "email"

    def send(self, address: str, items: list[AlertItem]) -> bool:
        if not items:
            return True
        subject, body = _render(items)
        return send_email(address, subject, body)
