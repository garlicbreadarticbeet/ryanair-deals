"""WhatsAppNotifier — STUB (interface bestaat, versturen volgt in Fase 2).

Het kanaal staat geregistreerd zodat de architectuur compleet is, maar send() doet niets
en gating (can_use) houdt 'channel:whatsapp' in Fase 1 dicht.
"""
from __future__ import annotations

from app.channels.base import AlertItem, register_notifier


@register_notifier
class WhatsAppNotifier:
    channel_type = "whatsapp"

    def send(self, address: str, items: list[AlertItem]) -> bool:
        # TODO(channel): WhatsApp Cloud API (template messages + expliciete opt-in). Fase 2.
        return False
