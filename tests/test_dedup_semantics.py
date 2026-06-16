"""Acceptatiecriterium 3: per-gebruiker dedup via sent_alerts reproduceert de
detect_new_deals-semantiek (nieuw / strikt goedkoper met epsilon), nu per kanaal.
"""
from __future__ import annotations

import datetime

from sqlalchemy import func, select

from app.core import dedup
from app.core.combine import ReturnDeal
from app.db.models import SentAlert

D1 = datetime.date(2026, 8, 1)
D2 = datetime.date(2026, 8, 4)


def _deal(total: float) -> ReturnDeal:
    return ReturnDeal("ryanair", "EIN", "BCN", 3, total, D1, D2, total / 2, total / 2)


def test_new_then_cheaper_semantics(db, make_user):
    user = make_user(origins=["EIN"])
    deal = _deal(30.0)

    prev = dedup.get_prev_alert(db, user.id, "telegram", deal)
    assert prev is None
    assert dedup.is_new_or_cheaper(prev, deal.total) is True  # nooit eerder → nieuw

    dedup.record_sent_alert(db, user.id, "telegram", deal)
    db.flush()

    prev = dedup.get_prev_alert(db, user.id, "telegram", deal)
    assert prev is not None and float(prev.alerted_price) == 30.0
    assert dedup.is_new_or_cheaper(prev, 30.0) is False           # zelfde prijs
    assert dedup.is_new_or_cheaper(prev, 30.0 - 0.0005) is False  # binnen epsilon
    assert dedup.is_new_or_cheaper(prev, 29.0) is True            # echt goedkoper


def test_dedup_is_per_channel(db, make_user):
    user = make_user(origins=["EIN"])
    deal = _deal(30.0)
    dedup.record_sent_alert(db, user.id, "telegram", deal)
    db.flush()

    prev_email = dedup.get_prev_alert(db, user.id, "email", deal)
    assert prev_email is None
    assert dedup.is_new_or_cheaper(prev_email, 30.0) is True  # ander kanaal → opnieuw melden


def test_record_upserts_to_cheaper_single_row(db, make_user):
    user = make_user(origins=["EIN"])
    dedup.record_sent_alert(db, user.id, "telegram", _deal(30.0))
    db.flush()
    dedup.record_sent_alert(db, user.id, "telegram", _deal(22.5))
    db.flush()

    prev = dedup.get_prev_alert(db, user.id, "telegram", _deal(22.5))
    assert float(prev.alerted_price) == 22.5
    count = db.execute(
        select(func.count()).select_from(SentAlert).where(SentAlert.user_id == user.id)
    ).scalar_one()
    assert count == 1  # upsert, geen dubbele rij
