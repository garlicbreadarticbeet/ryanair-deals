"""Regel 7 (GDPR): delete_user verwijdert via ON DELETE CASCADE alle gebruikersdata."""
from __future__ import annotations

import datetime

from sqlalchemy import func, select

from app.core import dedup
from app.core.combine import ReturnDeal
from app.db import repo
from app.db.models import Channel, Preference, SentAlert, User, UserOrigin


def test_delete_user_cascades(db, make_user):
    user = make_user(origins=["EIN", "NRN"])
    db.add(Channel(user_id=user.id, type="telegram", address="12345", verified=True))
    db.flush()
    dedup.record_sent_alert(
        db, user.id, "telegram",
        ReturnDeal("ryanair", "EIN", "BCN", 3, 30.0,
                   datetime.date(2026, 8, 1), datetime.date(2026, 8, 4), 15.0, 15.0),
    )
    db.flush()
    user_id = user.id

    repo.delete_user(db, user_id)
    db.flush()

    for model in (Preference, UserOrigin, Channel, SentAlert):
        count = db.execute(
            select(func.count()).select_from(model).where(model.user_id == user_id)
        ).scalar_one()
        assert count == 0, f"{model.__name__} niet opgeruimd"
    # Verse query (niet via identity-map) bevestigt dat de user echt weg is.
    assert db.execute(select(User).where(User.id == user_id)).scalar_one_or_none() is None
