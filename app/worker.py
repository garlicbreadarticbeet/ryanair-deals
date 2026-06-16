"""Worker-entrypoint: de ontkoppelde scan → match → notify-lus.

  python -m app.worker once            -> één keer scannen + alerten (cron / GitHub Actions)
  python -m app.worker run [--interval N]  -> blijven draaien (APScheduler), elke N minuten

Eén scan per run (op de gededupte unie van alle gekozen origins); daarna per actieve
gebruiker matchen tegen de voorkeuren en de nieuwe/goedkopere deals via de kanalen sturen.
"""
from __future__ import annotations

import argparse
import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.match import match_user
from app.core.scan import run_scan
from app.db.models import User
from app.db.session import session_scope
from app.dispatch import notify_user


def run_once(session: Session, today: datetime.date | None = None) -> dict:
    """Voer één volledige scan → match → notify-cyclus uit. Commit gebeurt door de caller.

    NB: notify verstuurt direct en schrijft sent_alerts pas na een bevestigde verzending;
    de uiteindelijke persistentie is de commit van de caller (at-least-once bij commit-fout).
    """
    deals = run_scan(session, today=today)
    users = session.execute(select(User).where(User.status == "active")).scalars().all()
    alerts = 0
    for user in users:
        matched = match_user(session, user, deals)
        if matched:
            alerts += notify_user(session, user, matched)
    return {"deals": len(deals), "users": len(users), "alerts": alerts}


def main_once() -> dict:
    """Eén run binnen een eigen transactie (commit bij succes)."""
    with session_scope() as session:
        stats = run_once(session)
    print(f"[worker] klaar: {stats}")
    return stats


def run_forever(interval_minutes: int = 240) -> None:
    """Blijf draaien met APScheduler; draait direct één keer en daarna elke N minuten."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()
    scheduler.add_job(main_once, "interval", minutes=interval_minutes)
    print(f"[worker] scheduler gestart — elke {interval_minutes} min. Eerste run nu...")
    main_once()
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Goedkoop Vliegen worker")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("once", help="één keer scannen + alerten")
    run_parser = sub.add_parser("run", help="blijven draaien (APScheduler)")
    run_parser.add_argument("--interval", type=int, default=240, help="minuten tussen runs (default 240)")

    args = parser.parse_args()
    if args.cmd == "once":
        main_once()
    else:
        run_forever(args.interval)


if __name__ == "__main__":
    main()
