"""Minimale FastAPI-app: health, e-mail magic-link, voorkeuren en account-verwijdering.

Klein gehouden (regel: "houd 'm klein"). Voorkeuren worden primair via de bot beheerd;
deze API biedt magic-link-onboarding + een voorkeuren-endpoint achter een sessietoken,
plus een GDPR-verwijderpad. Mollie-webhooks komen in Fase 2.
"""
from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts, billing
from app.billing import BillingError
from app.channels.email import send_email
from app.db.models import User, UserOrigin
from app.db.session import SessionLocal
from app.errors import PremiumRequired
from app.settings import settings
from app.web import auth

app = FastAPI(title="Goedkoop Vliegen API", version="0.1.0")


def get_db() -> Iterator[Session]:
    """Sessie per request: commit bij succes, rollback bij fout."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Haal de gebruiker uit een 'Authorization: Bearer <sessietoken>'-header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="ontbrekend sessietoken")
    user_id = auth.verify_session(db, authorization.split(" ", 1)[1])
    if user_id is None:
        raise HTTPException(status_code=401, detail="ongeldig of verlopen token")
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="geen actief account")
    return user


# ---------- schema's ----------

class EmailIn(BaseModel):
    email: str


class PrefsIn(BaseModel):
    threshold: float | None = None
    trip_lengths: list[int] | None = None
    alert_mode: str | None = None
    dest_filter_mode: str | None = None
    dest_whitelist: list[str] | None = None
    dest_blacklist: list[str] | None = None
    dest_countries: list[str] | None = None
    origins: list[str] | None = None  # vertrekvelden bij ryanair


class PrefsOut(BaseModel):
    threshold: float
    months_ahead: int
    currency: str
    alert_mode: str
    dest_filter_mode: str
    trip_lengths: list[int]
    dest_whitelist: list[str]
    dest_blacklist: list[str]
    dest_countries: list[str]
    origins: list[str]


def _prefs_out(db: Session, user: User) -> PrefsOut:
    prefs = user.preferences
    origins = list(
        db.execute(select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)).scalars()
    )
    return PrefsOut(
        threshold=float(prefs.threshold),
        months_ahead=prefs.months_ahead,
        currency=prefs.currency,
        alert_mode=prefs.alert_mode,
        dest_filter_mode=prefs.dest_filter_mode,
        trip_lengths=list(prefs.trip_lengths),
        dest_whitelist=list(prefs.dest_whitelist),
        dest_blacklist=list(prefs.dest_blacklist),
        dest_countries=list(prefs.dest_countries),
        origins=sorted(origins),
    )


# ---------- endpoints ----------

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/email", status_code=202)
def request_magic_link(body: EmailIn, db: Session = Depends(get_db)) -> dict:
    token = accounts.start_email_login(db, body.email)
    link = f"{settings.app_base_url}/auth/verify?token={token}"
    sent = send_email(
        body.email,
        "Je inloglink voor Goedkoop Vliegen",
        f'<p>Klik om in te loggen en je e-mail te bevestigen:</p><p><a href="{link}">{link}</a></p>',
    )
    return {"status": "verstuurd" if sent else "aangemaakt"}


@app.get("/auth/verify")
def verify_magic_link(token: str, db: Session = Depends(get_db)) -> dict:
    result = accounts.complete_email_login(db, token)
    if result is None:
        raise HTTPException(status_code=400, detail="ongeldige of verlopen link")
    _, session_token = result
    return {"status": "bevestigd", "session_token": session_token}


@app.get("/prefs", response_model=PrefsOut)
def get_prefs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> PrefsOut:
    return _prefs_out(db, user)


@app.put("/prefs", response_model=PrefsOut)
def put_prefs(
    body: PrefsIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> PrefsOut:
    prefs = user.preferences
    if body.threshold is not None:
        accounts.set_threshold(db, user, body.threshold)
    if body.trip_lengths is not None:
        accounts.set_trip_lengths(db, user, body.trip_lengths)
    if body.alert_mode is not None:
        prefs.alert_mode = body.alert_mode
    if body.dest_filter_mode is not None:
        prefs.dest_filter_mode = body.dest_filter_mode
    if body.dest_whitelist is not None:
        prefs.dest_whitelist = [d.upper() for d in body.dest_whitelist]
    if body.dest_blacklist is not None:
        prefs.dest_blacklist = [d.upper() for d in body.dest_blacklist]
    if body.dest_countries is not None:
        prefs.dest_countries = [c.lower() for c in body.dest_countries]
    if body.origins is not None:
        try:
            accounts.set_origins(db, user, "ryanair", body.origins)
        except PremiumRequired as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    db.flush()
    return _prefs_out(db, user)


@app.delete("/me", status_code=204)
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    accounts.delete_account(db, user)
    return Response(status_code=204)


# ---------- billing (Mollie-abonnement) ----------

@app.post("/billing/checkout")
def billing_checkout(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    try:
        url = billing.start_subscription_checkout(db, user)
    except BillingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"checkout_url": url}


@app.post("/billing/webhook")
async def billing_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    # Mollie POST't form-encoded met veld 'id'. Altijd 200 teruggeven (geen retry-storm);
    # eigen fouten loggen we maar laten we de afhandeling niet blokkeren.
    raw = (await request.body()).decode("utf-8")
    payment_id = parse_qs(raw).get("id", [None])[0]
    if payment_id:
        try:
            billing.handle_webhook(db, payment_id)
        except Exception as exc:  # noqa: BLE001
            print("billing-webhook-fout:", exc)
    return {"received": True}


@app.get("/billing/return")
def billing_return() -> dict:
    return {"status": "Betaling ontvangen — je account wordt zo bijgewerkt."}


@app.delete("/billing/subscription", status_code=204)
def billing_cancel(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    billing.cancel_subscription(db, user)
    return Response(status_code=204)
