"""Server-rendered website (HTML). Gebruikt de service-laag (accounts, billing) direct
en cookie-sessies voor auth. De JSON-API in main.py blijft daarnaast bestaan.
"""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts, billing
from app.alerts import render as alert_render
from app.alerts.enrich import enrich_deals
from app.billing import BillingError
from app.channels.base import AlertItem
from app.channels.email import send_login_email
from app.core import gating
from app.core.combine import deal_row_to_return_deal
from app.core.match import match_user
from app.db import repo
from app.db.models import Channel, Subscription, UserOrigin
from app.errors import PremiumRequired
from app.settings import settings
from app.web import content_store as content
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


@router.get("/api/airports")
def airports_search(q: str = "", db: Session = Depends(get_db)):
    """Luchthaven-zoeksuggesties (JSON) voor het zoek-en-kies veld op /preferences."""
    return JSONResponse(repo.search_airports(db, q))


@router.get("/", response_class=HTMLResponse)
def landing(user=Depends(optional_web_user)):
    faq_groups = content.faq_groups()
    faq_preview = faq_groups[0]["items"][:4] if faq_groups else []
    return render(
        "index.html", user=user, settings=settings,
        deals=content.destinations()[:6], origin_names=content.ORIGIN_NAMES,
        faq_preview=faq_preview,
    )


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
    sent = send_login_email(email, link)
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

# Bovengrens aan getoonde deal-kaarten (de scherpste eerst); filters helpen de rest vinden.
_MAX_DASHBOARD_DEALS = 60


def _sparkline(prices: list[float]) -> dict | None:
    """Maak SVG-polyline-punten van een prijsreeks (goedkoper = lager in de grafiek)."""
    if not prices or len(prices) < 3:
        return None
    w, h, pad = 120, 26, 3
    lo, hi = min(prices), max(prices)
    rng = (hi - lo) or 1.0
    n = len(prices)
    pts = [
        (round(pad + (w - 2 * pad) * i / (n - 1)), round(pad + (h - 2 * pad) * (hi - p) / rng))
        for i, p in enumerate(prices)
    ]
    return {
        "points": " ".join(f"{x},{y}" for x, y in pts),
        "lastx": pts[-1][0], "lasty": pts[-1][1],
        "down": prices[-1] <= prices[0],
    }


def _deal_vm(it: AlertItem, prices: list[float] | None, is_premium: bool) -> dict:
    """View-model voor één deal-kaart (gedeelde alert-render → leesbare velden)."""
    b = alert_render.badge(it)
    s = it.score
    return {
        "price": float(it.deal.total),
        "price_display": alert_render.money(it.deal.total),
        "dest": alert_render.destination_full(it),
        "city": alert_render.city_to(it),
        "flag": alert_render.flag(it.country_to),
        "country": alert_render.country_name(it),
        "country_code": it.country_to or "",
        "city_from": alert_render.city_from(it),
        "nights": it.deal.nights,
        "airline": it.deal.airline,
        "dates": alert_render.dates_label(it),
        "deeplink": alert_render.safe_href(it.deal.deeplink),
        "badge_text": b.text if b else None,
        "badge_tone": b.tone if b else None,
        "badge_emoji": b.emoji if b else None,
        "strength": s.strength if s else 0.0,
        "out_ord": it.deal.out_date.toordinal(),
        "history_days": s.days_span if (s and s.has_baseline) else 0,
        "spark": _sparkline(prices) if (is_premium and prices) else None,
    }


def _trip_summary(lengths) -> str:
    xs = sorted(set(int(n) for n in (lengths or [])))
    if not xs:
        return "—"
    if len(xs) == 1:
        return f"{xs[0]} nacht" if xs[0] == 1 else f"{xs[0]} nachten"
    if xs == list(range(xs[0], xs[-1] + 1)):
        return f"{xs[0]}–{xs[-1]} nachten"
    return ", ".join(map(str, xs)) + " nachten"


def _dest_summary(prefs) -> str:
    if prefs.dest_filter_mode == "country" and prefs.dest_countries:
        n = len(prefs.dest_countries)
        return f"{n} land" if n == 1 else f"{n} landen"
    if prefs.dest_filter_mode == "whitelist" and prefs.dest_whitelist:
        return f"{len(prefs.dest_whitelist)} bestemmingen"
    if prefs.dest_filter_mode == "blacklist" and prefs.dest_blacklist:
        return "bijna alles"
    return "alle bestemmingen"


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    prefs = user.preferences
    is_premium = user.tier == "premium"
    pairs = repo.allowed_provider_origins(db, user.id)
    origins = sorted({iata for _, iata in pairs})
    deals = [deal_row_to_return_deal(d) for d in repo.deals_for_origins(db, pairs)]
    matched = match_user(db, user, deals)

    enr = enrich_deals(db, matched)
    items: list[AlertItem] = []
    for d in matched:
        e = enr.get((d.provider, d.origin, d.destination, d.nights))
        items.append(AlertItem(
            deal=d,
            city_from=e.city_from if e else None,
            city_to=e.city_to if e else None,
            country_to=e.country_to if e else None,
            score=e.score if e else None,
        ))
    items.sort(key=alert_render.sort_key)        # spannendste deal eerst
    total_count = len(items)
    items = items[:_MAX_DASHBOARD_DEALS]

    series: dict = {}
    if is_premium and items:
        fps = {(it.deal.provider, it.deal.origin, it.deal.destination, it.deal.nights) for it in items}
        series = repo.price_series(db, fps, today=datetime.date.today())

    vms = [
        _deal_vm(it, series.get((it.deal.provider, it.deal.origin, it.deal.destination, it.deal.nights)), is_premium)
        for it in items
    ]

    cheapest = min(vms, key=lambda v: v["price"]) if vms else None
    discounts = [it.score.discount_pct for it in items
                 if it.score and it.score.has_baseline and it.score.discount_pct > 0]
    avg_discount = round(sum(discounts) / len(discounts)) if discounts else None

    connected = list(db.execute(
        select(Channel.type).where(
            Channel.user_id == user.id, Channel.verified.is_(True),
            Channel.opted_in_at.isnot(None), Channel.enabled.is_(True),
        )
    ).scalars())

    countries = sorted({(v["country_code"], v["country"]) for v in vms if v["country"]}, key=lambda x: x[1])
    nights_opts = sorted({v["nights"] for v in vms})

    return render(
        "dashboard.html", user=user, settings=settings, prefs=prefs,
        origins=origins, origin_names=content.ORIGIN_NAMES, has_origins=bool(origins),
        hero=(vms[0] if vms else None), deals=vms[1:], total_count=total_count, shown_count=len(vms),
        cheapest=cheapest, avg_discount=avg_discount, dest_summary=_dest_summary(prefs),
        trip_summary=_trip_summary(prefs.trip_lengths),
        connected_channels=connected, is_premium=is_premium,
        effective_mode=gating.effective_alert_mode(user),
        countries=countries, nights_opts=nights_opts, max_origins=gating.max_origins(user),
        active="dashboard",
    )


# ---------- voorkeuren ----------

def _render_preferences(db, user, *, flash=None, flash_kind=None, status_code=200):
    prefs = user.preferences
    origin_iatas = sorted(
        db.execute(select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)).scalars()
    )
    wl, bl = list(prefs.dest_whitelist or []), list(prefs.dest_blacklist or [])
    labels = repo.airport_labels(db, set(origin_iatas) | set(wl) | set(bl))

    def _chips(iatas):
        return [{"iata": i, "label": labels.get(i, i)} for i in iatas]

    prefs_data = {
        "maxOrigins": gating.max_origins(user),
        "isPremium": user.tier == "premium",
        "origins": _chips(origin_iatas),
        "tripLengths": [int(n) for n in (prefs.trip_lengths or [])],
        "destMode": prefs.dest_filter_mode or "all",
        "countries": [c.lower() for c in (prefs.dest_countries or [])],
        "whitelist": _chips(wl),
        "blacklist": _chips(bl),
    }
    return render(
        "preferences.html", status_code=status_code, user=user, settings=settings, prefs=prefs,
        is_premium=(user.tier == "premium"), max_origins=gating.max_origins(user),
        countries_options=content.DEST_COUNTRIES, prefs_data=prefs_data,
        flash=flash, flash_kind=flash_kind, active="preferences",
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
        # Gratis kan geen 'meteen': forceer 'één keer per dag' (ook als de UI omzeild wordt).
        prefs.alert_mode = "digest"
        flash, kind = "Opgeslagen. 'Meteen' kan alleen met Premium — je krijgt één keer per dag bericht.", "info"
    else:
        prefs.alert_mode = alert_mode if alert_mode in ("instant", "digest") else "digest"

    try:
        accounts.set_origins(db, user, settings.default_origin_provider, [t.upper() for t in _tokens(origins)])
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
    return render(
        "channels.html", user=user, settings=settings,
        telegram_connected="telegram" in chans, telegram_link=telegram_link, telegram_token=telegram_token,
        email=user.email, email_verified=user.email_verified,
        is_premium=(user.tier == "premium"), active="channels",
    )


# ---------- account + billing ----------

def _render_account(db, user, *, flash=None, flash_kind=None):
    sub = db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    return render(
        "account.html", user=user, settings=settings, subscription=sub,
        is_premium=(user.tier == "premium"), pricing=settings.premium_pricing,
        flash=flash, flash_kind=flash_kind, active="account",
    )


@router.get("/account", response_class=HTMLResponse)
def account_page(user=Depends(optional_web_user), db: Session = Depends(get_db), paid: str | None = None):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if paid == "1":
        return _render_account(
            db, user, flash="Betaling ontvangen — je account wordt zo bijgewerkt.", flash_kind="ok"
        )
    return _render_account(db, user)


@router.post("/upgrade")
def upgrade(user=Depends(optional_web_user), db: Session = Depends(get_db), plan: str = Form("annual")):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    try:
        url = billing.start_subscription_checkout(db, user, plan)
    except BillingError as exc:
        return _render_account(db, user, flash=str(exc), flash_kind="err")
    return RedirectResponse(url, status_code=303)


@router.post("/billing/cancel")
def billing_cancel_web(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    billing.cancel_subscription(db, user)
    return RedirectResponse("/account", status_code=303)


@router.post("/account/delete")
def account_delete(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    accounts.delete_account(db, user)
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response
