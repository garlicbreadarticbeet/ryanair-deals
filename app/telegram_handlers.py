"""Multi-user Telegram-commandologica (testbaar, zonder netwerk).

bot.py doet de polling en het versturen; deze module bepaalt per (chat_id, tekst) het
antwoord en voert de DB-mutaties uit via de accounts-service. Onboarding via /start
(met optioneel deeplink-token), voorkeuren via commando's, en /deals leest uit de
deals-tabel (geen live scan per gebruiker → geen API-belasting).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts
from app.core.combine import ReturnDeal, deal_row_to_return_deal
from app.core.match import match_user
from app.db import repo
from app.db.models import Airport, Channel, User, UserOrigin
from app.errors import PremiumRequired
from app.settings import settings

HELP = (
    "🤖 <b>Goedkoop Vliegen</b>\n\n"
    "/start — account aanmaken / koppelen\n"
    "/origins EIN NRN — je vertrekvelden instellen\n"
    "/drempel 50 — maximale retourprijs (€, heen+terug)\n"
    "/reisduren 3 5 7 — gewenste reisduren (nachten)\n"
    "/mij — je huidige instellingen\n"
    "/deals — je actuele deals onder je drempel\n"
    "/stop — account + gegevens verwijderen\n"
    "/help — deze uitleg"
)


def _user_for_chat(session: Session, chat_id: str) -> User | None:
    channel = session.execute(
        select(Channel).where(Channel.type == "telegram", Channel.address == str(chat_id))
    ).scalar_one_or_none()
    return session.get(User, channel.user_id) if channel else None


def _prefs_text(session: Session, user: User) -> str:
    prefs = user.preferences
    origins = sorted(
        session.execute(
            select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)
        ).scalars()
    )
    return (
        "⚙️ <b>Je instellingen</b>\n"
        f"Vertrekvelden: {', '.join(origins) or '(nog geen — /origins)'}\n"
        f"Drempel: €{float(prefs.threshold):.0f} (heen+terug)\n"
        f"Reisduren: {', '.join(map(str, prefs.trip_lengths))} dagen\n"
        f"Tier: {user.tier}"
    )


def _deals_text(session: Session, user: User) -> str:
    pairs = repo.allowed_provider_origins(session, user.id)
    if not pairs:
        return "Je hebt nog geen vertrekvelden ingesteld. Gebruik bijv. /origins EIN NRN."
    deals = [deal_row_to_return_deal(d) for d in repo.deals_for_origins(session, pairs)]
    matched = match_user(session, user, deals)
    if not matched:
        return f"Geen deals onder €{float(user.preferences.threshold):.0f} op dit moment."

    by_len: dict[int, list[ReturnDeal]] = {}
    for d in matched:
        by_len.setdefault(d.nights, []).append(d)
    lines = ["✈️ <b>Je actuele retour-deals</b> (prijs = heen+terug)"]
    for n in sorted(by_len):
        lines.append(f"\n<b>━━━ {n} dagen ━━━</b>")
        for d in sorted(by_len[n], key=lambda x: x.total)[:10]:
            lines.append(f"€{d.total:.2f} — {d.origin} ⇄ {d.destination} "
                         f"({d.out_date:%d-%m}→{d.in_date:%d-%m})")
    return "\n".join(lines)


def _set_origins(session: Session, user: User, args: list[str]) -> str:
    if not args:
        return "Gebruik: /origins EIN NRN"
    iatas = [a.upper() for a in args]
    known = set(
        session.execute(select(Airport.iata).where(Airport.iata.in_(iatas))).scalars()
    )
    unknown = [i for i in iatas if i not in known]
    if unknown:
        return f"Onbekende luchthaven(s): {', '.join(unknown)}."
    try:
        accounts.set_origins(session, user, settings.default_origin_provider, iatas)
    except PremiumRequired as exc:
        return str(exc)
    return f"Vertrekvelden bijgewerkt: {', '.join(iatas)}."


def handle_command(session: Session, chat_id: int | str, text: str) -> str:
    """Bepaal het antwoord op één Telegram-bericht en voer eventuele mutaties uit."""
    chat_id = str(chat_id)
    text = (text or "").strip()
    if not text:
        return ""
    parts = text.split()
    cmd = parts[0].lstrip("/").split("@")[0].lower()
    args = parts[1:]

    if cmd == "start":
        if args:  # deeplink-token: koppel aan bestaand account
            linked = accounts.link_telegram(session, args[0], chat_id)
            if linked is not None:
                return "✅ Je Telegram is gekoppeld aan je account. /mij voor je instellingen."
        _, created = accounts.get_or_create_telegram_user(session, chat_id)
        if created:
            return (
                "👋 Welkom! Je account is aangemaakt.\n"
                "Stel je vertrekvelden in met bijv. /origins EIN NRN, pas je drempel aan met "
                "/drempel 50, en bekijk je deals met /deals.\n/help voor alle commando's."
            )
        return "Welkom terug! /deals voor je actuele deals, /mij voor je instellingen."

    if cmd == "help":
        return HELP

    user = _user_for_chat(session, chat_id)
    if user is None:
        return "Stuur eerst /start om te beginnen."

    if cmd == "deals":
        return _deals_text(session, user)
    if cmd in ("mij", "instellingen"):
        return _prefs_text(session, user)
    if cmd in ("origins", "vertrek"):
        return _set_origins(session, user, args)
    if cmd in ("drempel", "threshold"):
        if not args:
            return "Gebruik: /drempel 45"
        try:
            accounts.set_threshold(session, user, float(args[0].replace(",", ".")))
        except ValueError:
            return "Ongeldig bedrag. Gebruik: /drempel 45"
        return f"Drempel ingesteld op €{float(user.preferences.threshold):.0f}."
    if cmd in ("reisduren", "triplengths"):
        if not args:
            return "Gebruik: /reisduren 3 5 7"
        try:
            lengths = sorted({int(a) for a in args})
        except ValueError:
            return "Ongeldige reisduren. Gebruik: /reisduren 3 5 7"
        accounts.set_trip_lengths(session, user, lengths)
        return f"Reisduren ingesteld op {', '.join(map(str, lengths))} dagen."
    if cmd == "stop":
        accounts.delete_account(session, user)
        return "Je account en gegevens zijn verwijderd. Tot ziens! 👋"

    return "Onbekend commando. /help voor de mogelijkheden."
