"""Server-rendered website (HTML). Gebruikt de service-laag (accounts, billing) direct
en cookie-sessies voor auth. De JSON-API in main.py blijft daarnaast bestaan.
"""
from __future__ import annotations

import datetime
import unicodedata

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
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
from app.db.models import Channel, Subscription, User, UserOrigin
from app.errors import PremiumRequired
from app.settings import settings
from app.web import content_store as content
from app.web import ratelimit
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


# Split-flap departure board (homepage-hero). Vaste tegelbreedtes per kolom zodat de
# tegels uitlijnen en er geen layout shift optreedt tijdens het flippen.
_BOARD_WIDTHS = {"from": 9, "to": 9, "price": 4, "nights": 2, "via": 3}
_AIRLINE_TAG = {"Ryanair": "RYR", "Wizz Air": "W6"}

_NL_MONTHS = ["", "januari", "februari", "maart", "april", "mei", "juni", "juli",
              "augustus", "september", "oktober", "november", "december"]


def _board_rows(destinations: list[dict]) -> list[dict]:
    """Bouw de bordrijen server-side: per cel een vaste-breedte glyph-string (zichtbaar bord,
    ook zonder JS) plus een leesbare waarde voor screenreaders. Alle items vormen samen de
    rotatie-pool voor de JS-animatie."""
    names = content.ORIGIN_NAMES
    rows: list[dict] = []
    for d in destinations:
        # NFC zodat één glyph = één code point (vaste-breedte tegels lijnen dan altijd uit).
        origin = unicodedata.normalize("NFC", names.get(d["origin"], d["origin"]))
        city = unicodedata.normalize("NFC", d["city"])
        tiles = {
            "from": origin.upper()[:9].ljust(9),
            "to": city.upper()[:9].ljust(9),
            "price": f"€{d['price']}"[:4].rjust(4),
            "nights": f"{d['nights']}N"[:2].ljust(2),
            "via": _AIRLINE_TAG.get(d["airline"], d["airline"][:3].upper()).ljust(3),
        }
        read = {
            "from": origin,
            "to": city,
            "price": f"{d['price']} euro",
            "nights": f"{d['nights']} nachten",
            "via": d["airline"],
        }
        rows.append({"tiles": tiles, "read": read})
    return rows


@router.get("/", response_class=HTMLResponse)
def landing(user=Depends(optional_web_user)):
    faq_groups = content.faq_groups()
    faq_preview = faq_groups[0]["items"][:4] if faq_groups else []
    destinations = content.destinations()
    return render(
        "index.html", user=user, settings=settings,
        deals=destinations[:6], board_rows=_board_rows(destinations),
        origin_names=content.ORIGIN_NAMES, faq_preview=faq_preview,
    )


# ---------- auth ----------

@router.get("/login", response_class=HTMLResponse)
def login_form(user=Depends(optional_web_user)):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render("login.html", user=None, settings=settings)


@router.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
    dev_link = None
    # Rate-limit per e-mail/IP: boven de limiet geen mail, maar dezelfde generieke bevestiging.
    if ratelimit.allow_login_email(db, email=email, ip=ratelimit.client_ip(request)):
        token = accounts.start_email_login(db, email)
        link = f"{settings.app_base_url}/verify?token={token}"
        sent = send_login_email(email, link)
        # Zonder e-mailprovider (dev) tonen we de link direct zodat je toch kunt inloggen.
        dev_link = None if (sent and settings.resend_api_key) else link
    return render("check_email.html", user=None, settings=settings, email=email, dev_link=dev_link)


@router.get("/verify")
def verify(request: Request, token: str, db: Session = Depends(get_db)):
    result = accounts.complete_email_login(db, token)
    if result is None:
        return render(
            "message.html", user=None, settings=settings, status_code=400,
            heading="Ongeldige of verlopen link",
            message="Deze inloglink werkt niet meer. Vraag een nieuwe aan.",
            link="/login", link_label="Opnieuw inloggen",
        )
    user, session_token = result
    # Koos iemand in de onboarding voor Premium? Open de checkout als overlay op /account
    # (met nette terugval naar de hosted checkout als JavaScript uit staat).
    dest = "/dashboard"
    plan_intent = request.cookies.get("vs_onboard_plan")
    if plan_intent in ("monthly", "annual") and user.tier != "premium":
        dest = f"/account?start={plan_intent}"
    response = RedirectResponse(dest, status_code=303)
    set_session_cookie(response, session_token)
    if plan_intent:
        response.delete_cookie("vs_onboard_plan", path="/")
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response


# ---------- onboarding ----------

def _render_onboarding(db, *, user=None, error=None, status_code=200):
    """Render de stap-voor-stap onboarding-wizard met de data die de client nodig heeft."""
    # Slanke deal-lijst voor de voorbeeld-stap (alleen wat de client nodig heeft; geen blurbs).
    deals = [
        {"origin": d["origin"], "city": d["city"], "country": d["country"],
         "price": d["price"], "nights": d["nights"], "airline": d["airline"]}
        for d in content.destinations()
    ]
    return render(
        "onboarding.html", status_code=status_code, user=user, settings=settings,
        airports=[{"iata": i, "name": n} for i, n in content.ORIGIN_NAMES.items()],
        deals=deals, pricing=settings.premium_pricing, error=error,
    )


def _apply_onboarding(db, user, *, threshold, trip_lengths, plan, origins, channel="email") -> None:
    """Pas de onboarding-antwoorden toe op de voorkeuren van deze (nieuwe) gebruiker."""
    accounts.set_threshold(db, user, threshold)
    lengths = sorted({int(t) for t in _tokens(trip_lengths) if t.isdigit()})
    accounts.set_trip_lengths(db, user, lengths or list(user.preferences.trip_lengths))
    # 'Meteen' is premium; gating.effective_alert_mode schaalt vanzelf af tot premium actief is.
    user.preferences.alert_mode = "instant" if plan in ("monthly", "annual") else "digest"
    # Vertrekvelden via set_origins (de enige bron van waarheid voor de gratis-limiet); bij
    # overschrijding cappen op de gratis-limiet (premium voegt later meer toe op /preferences).
    if origins:
        try:
            accounts.set_origins(db, user, settings.default_origin_provider, origins)
        except PremiumRequired:
            accounts.set_origins(
                db, user, settings.default_origin_provider, origins[: settings.free_max_origins]
            )
    # Kanaal-consent: koos iemand alléén Telegram, schakel het e-mailkanaal niet in als
    # alertkanaal (het blijft bestaan voor de login); Telegram koppelt de gebruiker daarna zelf.
    if channel == "telegram":
        em = db.execute(
            select(Channel).where(Channel.user_id == user.id, Channel.type == "email")
        ).scalar_one_or_none()
        if em is not None:
            em.enabled = False
    db.flush()


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_form(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    # Ingelogde gebruikers hebben al een account; voorkeuren wijzig je op /preferences.
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return _render_onboarding(db)


@router.post("/onboarding")
def onboarding_submit(
    request: Request,
    user=Depends(optional_web_user),
    db: Session = Depends(get_db),
    goal: str = Form(""),
    origins: list[str] = Form(default=[]),
    threshold: float = Form(50.0),
    trip_lengths: str = Form("3,5,7"),
    channel: str = Form("email"),
    plan: str = Form("free"),
    email: str = Form(""),
):
    # Ingelogd: onboarding muteert nooit een bestaand account (geen stille downgrade/dataverlies).
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)

    plan = plan if plan in ("free", "monthly", "annual") else "free"
    channel = channel if channel in ("email", "telegram", "both") else "email"
    origins = [o.strip().upper() for o in origins if o.strip()]
    threshold = min(500.0, max(10.0, threshold))   # clamp tot een redelijk bereik
    email = email.strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if "@" not in email or "." not in domain:
        return _render_onboarding(
            db, error="Vul een geldig e-mailadres in om je waakhond aan te zetten.", status_code=400
        )
    if not origins:
        return _render_onboarding(
            db, error="Kies minstens één vertrekveld, zodat we weten waar je vandaan vliegt.",
            status_code=400,
        )

    # Bestaand, geverifieerd account NOOIT muteren vanuit een anonieme request: stuur enkel de
    # inloglink (de eigenaar bevestigt zelf). Voorkomt ongeauthenticeerde writes op andermans account.
    existing = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    is_existing = existing is not None and existing.email_verified

    # Rate-limit per e-mail/IP: boven de limiet sturen we geen mail en muteren we niets, maar
    # tonen we dezelfde generieke bevestiging (anti-spam/kosten + geen makkelijkere enumeratie).
    dev_link = None
    if ratelimit.allow_login_email(db, email=email, ip=ratelimit.client_ip(request)):
        token = accounts.start_email_login(db, email)
        if not is_existing:
            target = existing or db.execute(
                select(User).where(func.lower(User.email) == email)
            ).scalar_one()
            _apply_onboarding(db, target, threshold=threshold, trip_lengths=trip_lengths,
                              plan=plan, origins=origins, channel=channel)
        link = f"{settings.app_base_url}/verify?token={token}"
        sent = send_login_email(email, link)
        dev_link = None if (sent and settings.resend_api_key) else link
    resp = render(
        "onboarding_done.html", user=None, settings=settings, email=email, dev_link=dev_link,
        plan=plan, channel=channel, pricing=settings.premium_pricing,
        telegram_username=settings.telegram_bot_username,
    )
    if plan in ("monthly", "annual") and not is_existing:
        # Onthoud de premium-keuze zodat /verify na bevestiging meteen de checkout opent.
        resp.set_cookie(
            "vs_onboard_plan", plan, max_age=1800, httponly=True, samesite="lax", path="/",
            secure=settings.app_base_url.startswith("https"),
        )
    return resp


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

def _render_account(db, user, *, flash=None, flash_kind=None, start_checkout=None):
    sub = db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    return render(
        "account.html", user=user, settings=settings, subscription=sub,
        is_premium=(user.tier == "premium"), pricing=settings.premium_pricing,
        flash=flash, flash_kind=flash_kind, start_checkout=start_checkout, active="account",
    )


@router.get("/account", response_class=HTMLResponse)
def account_page(
    user=Depends(optional_web_user), db: Session = Depends(get_db),
    paid: str | None = None, canceled: str | None = None, start: str | None = None,
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if paid == "1":
        return _render_account(
            db, user, flash="Betaling ontvangen, je account wordt zo bijgewerkt.", flash_kind="ok"
        )
    if canceled == "1":
        return _render_account(
            db, user, flash="Je Premium is opgezegd. Je houdt je toegang tot het einde van de "
            "lopende periode; daarna word je niet meer geïncasseerd.", flash_kind="ok",
        )
    # ?start=monthly|annual komt van de onboarding-premium-keuze: open de checkout-overlay.
    return _render_account(db, user, start_checkout=start if start in ("monthly", "annual") else None)


@router.post("/upgrade")
def upgrade(user=Depends(optional_web_user), db: Session = Depends(get_db), plan: str = Form("annual")):
    """No-JS-terugval: server-redirect naar de hosted checkout (de JS-overlay gebruikt /billing/checkout-url)."""
    if user is None:
        return RedirectResponse("/login", status_code=303)
    try:
        url = billing.start_subscription_checkout(db, user, plan)
    except BillingError as exc:
        return _render_account(db, user, flash=str(exc), flash_kind="err")
    return RedirectResponse(url, status_code=303)


@router.post("/billing/checkout-url")
def billing_checkout_url(
    user=Depends(optional_web_user), db: Session = Depends(get_db), plan: str = Form("annual"),
):
    """Geef de checkout-URL als JSON terug, voor de Lemon Squeezy-overlay op de eigen site."""
    if user is None:
        return JSONResponse({"error": "niet ingelogd"}, status_code=401)
    plan = plan if plan in ("monthly", "annual") else "annual"
    try:
        url = billing.start_subscription_checkout(db, user, plan)
    except BillingError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"url": url})


@router.get("/account/cancel", response_class=HTMLResponse)
def cancel_confirm(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    """Bevestigingsstap vóór het opzeggen: laat de gevolgen zien i.p.v. direct te annuleren."""
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.tier != "premium":
        return RedirectResponse("/account", status_code=303)
    sub = db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    period_end = None
    if sub and sub.current_period_end:
        d = sub.current_period_end
        period_end = f"{d.day} {_NL_MONTHS[d.month]} {d.year}"
    return render(
        "cancel_confirm.html", user=user, settings=settings, subscription=sub,
        period_end=period_end, pricing=settings.premium_pricing, active="account",
    )


@router.post("/billing/cancel")
def billing_cancel_web(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.tier == "premium":          # alleen opzeggen als er iets te annuleren valt
        billing.cancel_subscription(db, user)
    return RedirectResponse("/account?canceled=1", status_code=303)


@router.post("/account/delete")
def account_delete(user=Depends(optional_web_user), db: Session = Depends(get_db)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    accounts.delete_account(db, user)
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response
