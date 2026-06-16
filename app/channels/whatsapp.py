"""WhatsAppNotifier — verzending via de WhatsApp Cloud API, achter een feature-flag.

Interface + verzendlogica zijn compleet, maar `send()` is een no-op zolang
`settings.whatsapp_enabled` uit staat of credentials ontbreken (Fase 2: "interface klaar,
nog niet live"). Gating (channel:whatsapp = premium) zit in core/gating via settings.
"""
from __future__ import annotations

from app.channels.base import AlertItem, register_notifier
from app.net import get_session
from app.settings import settings

_GRAPH = "https://graph.facebook.com/v21.0"


def format_alerts(items: list[AlertItem]) -> str:
    """Platte tekst (WhatsApp ondersteunt geen HTML)."""
    lines = [f"✈️ {len(items)} nieuwe retour-deal(s):"]
    for it in sorted(items, key=lambda x: x.deal.total):
        d = it.deal
        drop = f" (was €{it.previous_price:.2f})" if it.previous_price else ""
        lines.append(
            f"€{d.total:.2f}{drop} — {d.origin}⇄{d.destination}, {d.nights}d "
            f"({d.out_date:%d-%m}→{d.in_date:%d-%m})"
        )
    return "\n".join(lines)


@register_notifier
class WhatsAppNotifier:
    channel_type = "whatsapp"

    def send(self, address: str, items: list[AlertItem]) -> bool:
        if not items:
            return True
        # Niet live tot de feature-flag aan staat én credentials aanwezig zijn.
        if not (settings.whatsapp_enabled and settings.whatsapp_token and settings.whatsapp_phone_id):
            return False
        # TODO(channel): business-initiated berichten buiten het 24u-venster vereisen een
        #   goedgekeurde WhatsApp-template i.p.v. een vrij tekstbericht. Hier nu type=text.
        try:
            resp = get_session().post(
                f"{_GRAPH}/{settings.whatsapp_phone_id}/messages",
                headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": str(address),
                    "type": "text",
                    "text": {"body": format_alerts(items)},
                },
                timeout=20,
            )
            return resp.status_code in (200, 201)
        except Exception:
            return False
