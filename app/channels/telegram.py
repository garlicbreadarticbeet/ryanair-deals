"""TelegramNotifier — verzending via de bestaande notify.send_telegram (requests+certifi).

De opmaak gebruikt de gedeelde alert-presentatielaag (app/alerts/render): stadsnamen + vlag,
de dealscore-badge ("🔥 38% onder normaal" / "laagste in N dagen") en een nette boekknop.
De items komen al op dealsterkte gesorteerd uit de dispatcher (spannendste bovenaan).
"""
from __future__ import annotations

import html

import notify  # bestaande sender (root-module)

from app.alerts import render as R
from app.channels.base import AlertItem, register_notifier
from app.net import get_session
from app.settings import settings

_API = "https://api.telegram.org/bot"


def _deal_block(it: AlertItem) -> str:
    d = it.deal
    b = R.badge(it)
    badge = f"   {b.emoji} <i>{html.escape(b.text)}</i>" if b else ""
    airline = f" · {html.escape(d.airline)}" if d.airline else ""
    href = R.safe_href(d.deeplink)
    link = (
        f'\n   <a href="{html.escape(href, quote=True)}">→ Bekijk de vlucht</a>'
        if href else ""
    )
    return (
        f"\n\n<b>{R.money(d.total)}</b> · <b>{html.escape(R.city_to(it))}</b> "
        f"{R.flag(it.country_to)}{badge}"
        f"\n   vanaf {html.escape(R.city_from(it))} · {R.nights_label(it)}{airline}"
        f"\n   {R.dates_label(it)}{link}"
    )


def format_alerts(items: list[AlertItem]) -> str:
    """Telegram-HTML: gerangschikt op dealsterkte, met stadsnaam, vlag en dealscore-badge."""
    n = len(items)
    head = f"✈️ <b>{n} nieuwe {'deal' if n == 1 else 'deals'}</b> onder je drempel"
    parts = [head]
    parts.extend(_deal_block(it) for it in items)
    parts.append("\n\n<i>Prijzen kunnen wijzigen; je boekt zelf bij de airline.</i>")
    return "".join(parts)


def _photo_caption(it: AlertItem) -> str:
    """Korte HTML-caption bij de hero-foto: de beste deal in één regel."""
    b = R.badge(it)
    badge = f" · {b.emoji} {html.escape(b.text)}" if b else ""
    return (
        f"✈️ <b>{R.money(it.deal.total)}</b> · <b>{html.escape(R.city_to(it))}</b> "
        f"{R.flag(it.country_to)}{badge}"
    )


def _send_photo(chat_id: str, png: bytes, caption: str) -> bool:
    """Stuur een foto-bericht (sendPhoto) met de gebrande dealkaart. Best-effort."""
    token = settings.telegram_bot_token
    if not token:
        return False
    try:
        resp = get_session().post(
            f"{_API}{token}/sendPhoto",
            data={"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("deal.png", png, "image/png")},
            timeout=30,
        )
        return bool(resp.json().get("ok"))
    except Exception:  # noqa: BLE001
        return False


@register_notifier
class TelegramNotifier:
    channel_type = "telegram"

    def send(self, address: str, items: list[AlertItem]) -> bool:
        if not items:
            return True
        # Lazy import: voorkomt een circulaire import (card → render → channels.base → telegram).
        from app.alerts.card import render_deal_card

        # Visuele hero (beste deal als foto) is best-effort; het tekstbericht met álle deals
        # + boeklinks is de bron van waarheid voor "verzonden" (drijft de dedup).
        card = render_deal_card(items[0])
        if card:
            _send_photo(address, card, _photo_caption(items[0]))
        return notify.send_telegram(format_alerts(items), chat_id=address)
