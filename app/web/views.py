"""Server-rendered website (HTML). Gebruikt de service-laag (accounts, billing) direct
en cookie-sessies voor auth. De JSON-API in main.py blijft daarnaast bestaan.
"""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts
from app.channels.email import send_email
from app.core import gating
from app.core.combine import deal_row_to_return_deal
from app.core.match import match_user
from app.db import repo
from app.db.models import Channel, UserOrigin
from app.errors import PremiumRequired
from app.settings import settings
from app.web.auth import issue_token
from app.web.deps import (
    clear_session_cookie,
    get_db,
    optional_web_user,
    set_session_cookie,
)
from app.web.templating import render

router = APIRouter()


def _tokens(raw: str) -> list[str]:
    return [t for t in raw.replace(",", " ").split() if t]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@router.get("/", response_class=HTMLResponse)
def landing(user=Depends(optional_web_user)):
    return render("index.html", user=user, settings=settings)


# ---------- auth ----------

@router.get("/login", response_class=HTMLResponse)
def login_form(user=Depends(optional_web_user)):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render("login.html", user=None, settings=settings)


@router.post("/login", response_class=HTMLResponse)
def login_submit(email: str = Form(...), db: Session = Depends(get_db)):
    token = accounts.start_email_login(db, email)
    link = f"{settings.app_base_url}/verify?token={token}"
    sent = send_email(
        email,
        "Je inloglink voor Goedkoop Vliegen",
        f'<p>Klik om in te loggen en je e-mail te bevestigen:</p><p><a href="{link}">{link}</a></p>',
    )
    # Zonder e-mailprovider (dev) tonen we de link direct zodat je toch kunt inloggen.
    dev_link = None if (sent and settings.resend_api_key) else link
    return render("check_email.html", user=None, settings=settings, email=email, dev_link=dev_link)


@router.get("/verify")
def verify(token: str, db: Session = Depends(get_db)):
    result = accounts.complete_email_login(db, token)
    if result is None:
        return render(
            "message.html", user=None, settings=settings, status_code=400,
            heading="Ongeldige of verlopen link",
            message="Deze inloglink werkt niet meer. Vraag een nieuwe aan.",
            link="/login", link_label="Opnieuw inloggen",
        )
    _, session_token = result
    response = RedirectResponse("/dashboard", status_code=303)
    set_session_cookie(response, session_token)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response


# ---------- dashboard ----------

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    pairs = repo.allowed_provider_origins(db, user.id)
    origins = sorted({iata for _, iata in pairs})
    deals = [deal_row_to_return_deal(d) for d in repo.deals_for_origins(db, pairs)]
    matched = match_user(db, user, deals)
    by_len: dict[int, list] = {}
    for d in matched:
        by_len.setdefault(d.nights, []).append(d)
    deal_groups = [
        {"nights": n, "deals": sorted(by_len[n], key=lambda x: x.total)} for n in sorted(by_len)
    ]
    return render(
        "dashboard.html", user=user, settings=settings, prefs=user.preferences,
        origins=origins, has_origins=bool(origins), deal_groups=deal_groups,
        effective_mode=gating.effective_alert_mode(user),
    )


# ---------- voorkeuren ----------

def _render_preferences(db, user, *, flash=None, flash_kind=None, status_code=200):
    prefs = user.preferences
    origins = " ".join(
        sorted(db.execute(select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)).scalars())
    )
    return render(
        "preferences.html", status_code=status_code, user=user, settings=settings, prefs=prefs,
        origins=origins, trip_lengths=" ".join(map(str, prefs.trip_lengths)),
        dest_countries=" ".join(prefs.dest_countries), dest_whitelist=" ".join(prefs.dest_whitelist),
        dest_blacklist=" ".join(prefs.dest_blacklist),
        is_premium=(user.tier == "premium"), max_origins=gating.max_origins(user),
        flash=flash, flash_kind=flash_kind,
    )


@router.get("/preferences", response_class=HTMLResponse)
def preferences_form(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return _render_preferences(db, user)


@router.post("/preferences", response_class=HTMLResponse)
def preferences_save(
    user=Depends(optional_web_user),
    db: Session = Depends(get_db),
    origins: str = Form(""),
    threshold: float = Form(...),
    trip_lengths: str = Form(""),
    alert_mode: str = Form("digest"),
    dest_filter_mode: str = Form("all"),
    dest_countries: str = Form(""),
    dest_whitelist: str = Form(""),
    dest_blacklist: str = Form(""),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    prefs = user.preferences
    flash, kind = "Voorkeuren opgeslagen.", "ok"

    accounts.set_threshold(db, user, threshold)
    lengths = sorted({int(t) for t in _tokens(trip_lengths) if t.isdigit()}) or list(prefs.trip_lengths)
    accounts.set_trip_lengths(db, user, lengths)
    prefs.dest_filter_mode = dest_filter_mode if dest_filter_mode in (
        "all", "country", "whitelist", "blacklist") else "all"
    prefs.dest_countries = [t.lower() for t in _tokens(dest_countries)]
    prefs.dest_whitelist = [t.upper() for t in _tokens(dest_whitelist)]
    prefs.dest_blacklist = [t.upper() for t in _tokens(dest_blacklist)]

    if alert_mode == "instant" and not gating.can_use(user, "mode:instant"):
        prefs.alert_mode = "instant"
        flash, kind = "Opgeslagen. Instant is premium — voorlopig krijg je de dagelijkse digest.", "info"
    else:
        prefs.alert_mode = alert_mode if alert_mode in ("instant", "digest") else "digest"

    try:
        accounts.set_origins(db, user, "ryanair", [t.upper() for t in _tokens(origins)])
    except PremiumRequired as exc:
        flash, kind = str(exc), "err"
    db.flush()
    return _render_preferences(db, user, flash=flash, flash_kind=kind)


# ---------- kanalen ----------

@router.get("/channels", response_class=HTMLResponse)
def channels_page(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    chans = {c.type: c for c in db.execute(
        select(Channel).where(Channel.user_id == user.id)).scalars()}
    telegram_link = telegram_token = None
    if "telegram" not in chans:
        telegram_token = issue_token(db, "telegram_link", user_id=user.id)
        if settings.telegram_bot_username:
            telegram_link = f"https://t.me/{settings.telegram_bot_username}?start={telegram_token}"
    wa = chans.get("whatsapp")
    return render(
        "channels.html", user=user, settings=settings,
        telegram_connected="telegram" in chans, telegram_link=telegram_link, telegram_token=telegram_token,
        email=user.email, email_verified=user.email_verified,
        is_premium=(user.tier == "premium"), whatsapp_number=(wa.address if wa else None),
    )


@router.post("/channels/whatsapp")
def channels_whatsapp(
    user=Depends(optional_web_user), db: Session = Depends(get_db), number: str = Form(...)
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if not gating.can_use(user, "channel:whatsapp"):
        return RedirectResponse("/account", status_code=303)
    existing = db.execute(
        select(Channel).where(Channel.type == "whatsapp", Channel.user_id == user.id)
    ).scalar_one_or_none()
    if existing is not None:
        existing.address = number.strip()
        existing.verified = True
        existing.opted_in_at = _utcnow()
        existing.enabled = True
    else:
        db.add(Channel(user_id=user.id, type="whatsapp", address=number.strip(),
                       verified=True, opted_in_at=_utcnow(), enabled=True))
    db.flush()
    return RedirectResponse("/channels", status_code=303)
