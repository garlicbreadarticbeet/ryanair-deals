"""Worker-entrypoint: de ontkoppelde scan → match → notify-lus.

  python -m app.worker once                -> één scan + instant-alerts (cron / GitHub Actions)
  python -m app.worker digest              -> één digest-ronde (dagelijkse bundel)
  python -m app.worker run [--interval N]  -> blijven draaien: instant elke N min + dagelijkse digest

Eén scan per run (op de gededupte unie van alle gekozen origins). Daarna:
- **instant** (premium die instant koos): direct melden met de verse deals;
- **digest** (gratis of premium-met-digest): één keer per dag bundelen uit de deals-tabel.

Beide delen de per-kanaal dedup (sent_alerts), dus een deal gaat per kanaal maar één keer uit.
"""
from __future__ import annotations

import argparse
import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import gating
from app.core.combine import deal_row_to_return_deal
from app.core.match import match_user
from app.core.scan import run_scan
from app.db import repo
from app.db.models import User
from app.db.session import session_scope
from app.dispatch import notify_user


def _active_users(session: Session) -> list[User]:
    return list(session.execute(select(User).where(User.status == "active")).scalars())


def run_once(session: Session, today: datetime.date | None = None) -> dict:
    """Scan + instant-notify. Commit gebeurt door de caller.

    Notify verstuurt direct en schrijft sent_alerts pas na een bevestigde verzending; de
    uiteindelijke persistentie is de commit van de caller (at-least-once bij commit-fout).
    """
    deals = run_scan(session, today=today)
    users = _active_users(session)
    alerts = 0
    for user in users:
        if gating.effective_alert_mode(user) != "instant":
            continue
        matched = match_user(session, user, deals)
        if matched:
            alerts += notify_user(session, user, matched)
    return {"deals": len(deals), "users": len(users), "alerts": alerts, "mode": "instant"}


def run_digest(session: Session) -> dict:
    """Dagelijkse bundel voor digest-gebruikers, o.b.v. de gepersisteerde deals-tabel."""
    users = _active_users(session)
    alerts = 0
    digest_users = 0
    for user in users:
        if gating.effective_alert_mode(user) != "digest":
            continue
        digest_users += 1
        pairs = repo.allowed_provider_origins(session, user.id)
        deals = [deal_row_to_return_deal(d) for d in repo.deals_for_origins(session, pairs)]
        matched = match_user(session, user, deals)
        if matched:
            alerts += notify_user(session, user, matched)
    return {"users": digest_users, "alerts": alerts, "mode": "digest"}


def main_once() -> dict:
    with session_scope() as session:
        stats = run_once(session)
    print(f"[worker] instant klaar: {stats}")
    return stats


def main_digest() -> dict:
    with session_scope() as session:
        stats = run_digest(session)
    print(f"[worker] digest klaar: {stats}")
    return stats


def run_forever(interval_minutes: int = 240, digest_hour: int = 8) -> None:
    """Blijf draaien: instant-scan elke N min + dagelijkse digest om digest_hour:00."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()
    scheduler.add_job(main_once, "interval", minutes=interval_minutes, id="instant")
    scheduler.add_job(main_digest, "cron", hour=digest_hour, minute=0, id="digest")
    print(f"[worker] gestart — instant elke {interval_minutes} min, digest om {digest_hour}:00. Eerste run nu...")
    main_once()
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Goedkoop Vliegen worker")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("once", help="één scan + instant-alerts")
    sub.add_parser("digest", help="één digest-ronde")
    run_parser = sub.add_parser("run", help="blijven draaien (APScheduler)")
    run_parser.add_argument("--interval", type=int, default=240, help="minuten tussen instant-runs")
    run_parser.add_argument("--digest-hour", type=int, default=8, help="uur van de dagelijkse digest")

    args = parser.parse_args()
    if args.cmd == "once":
        main_once()
    elif args.cmd == "digest":
        main_digest()
    else:
        run_forever(args.interval, args.digest_hour)


if __name__ == "__main__":
    main()
