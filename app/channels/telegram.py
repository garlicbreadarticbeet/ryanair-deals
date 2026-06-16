"""TelegramNotifier — hergebruikt de bestaande notify.send_telegram (requests+certifi)
en de bewezen alert-opmaak, maar nu met de chat_id per kanaal i.p.v. de env-eigenaar.
"""
from __future__ import annotations

import html

import notify  # bestaande sender (root-module)
from app.channels.base import AlertItem, register_notifier

# NL-datumhelpers hergebruiken uit de bestaande CLI-laag (geen duplicatie).
from deals import fmt_full


def format_alerts(items: list[AlertItem]) -> str:
    """Telegram-HTML: gegroepeerd per reisduur, met "was €X" bij een goedkopere deal."""
    head = f"✈️ <b>{len(items)} nieuwe retour-deal(s)</b>"
    parts = [head]
    by_len: dict[int, list[AlertItem]] = {}
    for it in items:
        by_len.setdefault(it.deal.nights, []).append(it)
    for n in sorted(by_len):
        parts.append(f"\n\n<b>━━━ {n} dagen ━━━</b>")
        for it in sorted(by_len[n], key=lambda x: x.deal.total):
            d = it.deal
            drop = f" (was €{it.previous_price:.2f})" if it.previous_price else ""
            parts.append(
                f"\n<b>€{d.total:.2f}</b>{drop} — "
                f"{html.escape(d.origin)} ⇄ {html.escape(d.destination)}\n"
                f"   heen {fmt_full(d.out_date)} · terug {fmt_full(d.in_date)}"
            )
    return "".join(parts)


@register_notifier
class TelegramNotifier:
    channel_type = "telegram"

    def send(self, address: str, items: list[AlertItem]) -> bool:
        if not items:
            return True
        return notify.send_telegram(format_alerts(items), chat_id=address)
