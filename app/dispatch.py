"""Notify-dispatcher: stuurt de gematchte deals van één gebruiker naar diens kanalen.

Bridge tussen core (dedup, gating) en channels (Notifier-registry). Bewust BUITEN core/,
zodat core kanaal-agnostisch blijft. Kernregels:
- alleen geverifieerde, opted-in, enabled kanalen;
- can_use(user, "channel:<type>") beslist (Fase 2-gating-naad);
- per kanaal de "nieuw of goedkoper"-dedup;
- sent_alerts pas schrijven NA een bevestigde verzending (mislukte send dedupt niet stil).
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.alerts.enrich import enrich_deals
from app.alerts.render import sort_key
from app.channels.base import AlertItem, get_notifier
from app.core import dedup
from app.core.combine import ReturnDeal
from app.core.gating import can_use
from app.db.models import User

# Bovengrens per kanaal per run: een gerichte "top-deals"-melding i.p.v. een muur. De
# spannendste (sterkste dealscore) gaan eerst; de rest komt een volgende run aan bod
# (ze worden niet als verzonden gemarkeerd, dus blijven kandidaat).
_MAX_ALERTS_PER_RUN = 12


def notify_user(session: Session, user: User, matched_deals: Iterable[ReturnDeal]) -> int:
    """Verstuur de gematchte deals naar de actieve kanalen van ``user``.

    Retourneert het aantal verstuurde (deal × kanaal)-meldingen.
    """
    deals = list(matched_deals)
    if not deals:
        return 0

    # Verrijk één keer (stadsnamen, bestemmingsland, dealscore) — gedeeld over alle kanalen.
    enrichment = enrich_deals(session, deals)

    sent = 0
    for channel in user.channels:
        if not (channel.enabled and channel.verified and channel.opted_in_at is not None):
            continue
        if not can_use(user, f"channel:{channel.type}"):
            continue
        notifier = get_notifier(channel.type)
        if notifier is None:
            continue

        # Per-kanaal dedup: alleen nieuwe of goedkopere deals.
        items: list[AlertItem] = []
        for deal in deals:
            prev = dedup.get_prev_alert(session, user.id, channel.type, deal)
            if dedup.is_new_or_cheaper(prev, deal.total):
                enr = enrichment.get((deal.provider, deal.origin, deal.destination, deal.nights))
                items.append(AlertItem(
                    deal=deal,
                    previous_price=float(prev.alerted_price) if prev else None,
                    city_from=enr.city_from if enr else None,
                    city_to=enr.city_to if enr else None,
                    country_to=enr.country_to if enr else None,
                    score=enr.score if enr else None,
                ))
        if not items:
            continue

        # Spannendste deals bovenaan (sterkste dealscore, dan goedkoopste); capped per run.
        items.sort(key=sort_key)
        items = items[:_MAX_ALERTS_PER_RUN]
        if notifier.send(channel.address, items):
            for item in items:
                dedup.record_sent_alert(session, user.id, channel.type, item.deal)
            sent += len(items)
    return sent
