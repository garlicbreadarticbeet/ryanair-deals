"""Multi-user Telegram-commando's: onboarding, voorkeuren, /deals uit de DB, /stop."""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import select

from app import telegram_handlers as th
from app.db.models import Channel, Deal
from app.web import auth


def test_start_creates_account(db):
    reply = th.handle_command(db, 111, "/start")
    assert "aangemaakt" in reply.lower()
    channel = db.execute(
        select(Channel).where(Channel.address == "111", Channel.type == "telegram")
    ).scalar_one()
    assert channel.verified and channel.opted_in_at is not None

    again = th.handle_command(db, 111, "/start")
    assert "terug" in again.lower()


def test_start_with_deeplink_links_existing_account(db, make_user):
    user = make_user()
    token = auth.issue_token(db, "telegram_link", user_id=user.id)
    reply = th.handle_command(db, 222, f"/start {token}")
    assert "gekoppeld" in reply.lower()
    channel = db.execute(select(Channel).where(Channel.address == "222")).scalar_one()
    assert channel.user_id == user.id


def test_command_requires_start_first(db):
    assert "start" in th.handle_command(db, 333, "/deals").lower()


def test_set_preferences_and_show(db):
    th.handle_command(db, 444, "/start")
    th._user_for_chat(db, 444).tier = "premium"  # 2 origins → premium
    db.flush()
    assert "EIN" in th.handle_command(db, 444, "/origins ein nrn")
    assert "40" in th.handle_command(db, 444, "/drempel 40")
    assert "3" in th.handle_command(db, 444, "/reisduren 3 5")
    overview = th.handle_command(db, 444, "/mij")
    assert "EIN" in overview and "NRN" in overview and "40" in overview


def test_free_origin_limit_message(db):
    th.handle_command(db, 445, "/start")  # gratis
    reply = th.handle_command(db, 445, "/origins ein nrn")
    assert "premium" in reply.lower()  # nette upgrade-melding i.p.v. crash


def test_unknown_origin_rejected(db):
    th.handle_command(db, 555, "/start")
    assert "onbekend" in th.handle_command(db, 555, "/origins ZZZ").lower()


def test_deals_reads_from_db_and_filters(db):
    th.handle_command(db, 666, "/start")
    th.handle_command(db, 666, "/origins EIN")
    th.handle_command(db, 666, "/drempel 50")

    db.add(Deal(provider="ryanair", origin="EIN", destination="BCN", nights=3,
                out_date=datetime.date(2026, 8, 1), in_date=datetime.date(2026, 8, 4),
                out_price=Decimal("20.00"), in_price=Decimal("15.00"),
                total_price=Decimal("35.00"), currency="EUR"))
    db.add(Deal(provider="ryanair", origin="EIN", destination="AGP", nights=3,
                out_date=datetime.date(2026, 8, 1), in_date=datetime.date(2026, 8, 4),
                out_price=Decimal("60.00"), in_price=Decimal("60.00"),
                total_price=Decimal("120.00"), currency="EUR"))
    db.flush()

    reply = th.handle_command(db, 666, "/deals")
    assert "EIN ⇄ BCN" in reply
    assert "35.00" in reply
    assert "AGP" not in reply  # boven drempel → niet getoond


def test_stop_deletes_account(db):
    th.handle_command(db, 777, "/start")
    assert "verwijderd" in th.handle_command(db, 777, "/stop").lower()
    assert db.execute(select(Channel).where(Channel.address == "777")).scalar_one_or_none() is None
