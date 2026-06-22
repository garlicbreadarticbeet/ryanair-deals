"""Rate-limiting voor de mail-versturende auth-endpoints (magic-link).

POST /login, POST /onboarding en POST /auth/email sturen elk een magic-link-mail via Resend.
Zonder begrenzing is dat een spam-/kostenvector (Resend rekent per mail) en maakt het
account-enumeratie iets makkelijker. We tellen recente pogingen per sleutel — zowel per
e-mailadres als per IP — in een glijdend venster en weigeren boven de limiet.

Bewust simpel en stateless in de app-laag: de teller leeft in Postgres (al beschikbaar),
zodat hij over meerdere web-workers klopt zonder extra infra (Redis). De caller toont bij
weigering dezelfde generieke bevestiging als bij succes, zodat enumeratie niet makkelijker wordt.
"""
from __future__ import annotations

import datetime

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuthThrottle
from app.settings import settings


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def client_ip(request: Request) -> str:
    """Het echte client-IP. Uvicorn draait met ``--proxy-headers``, dus ``request.client.host``
    is het door Caddy doorgegeven X-Forwarded-For-IP (niet dat van de proxy zelf)."""
    return request.client.host if request.client else ""


def allow_login_email(session: Session, *, email: str, ip: str = "") -> bool:
    """True als er nog een magic-link-mail voor dit e-mailadres/IP verstuurd mag worden.

    Telt de pogingen binnen het venster per sleutel; bij overschrijding van de limiet (op
    e-mail óf IP) → False, en de caller verstuurt dan geen mail. Wordt de poging toegestaan,
    dan registreren we hem (per sleutel) zodat hij meetelt voor de volgende aanvraag.
    """
    email = (email or "").strip().lower()
    cutoff = _now() - datetime.timedelta(minutes=settings.login_mail_rate_window_minutes)
    keys = [("email", email)]
    if ip:
        keys.append(("ip", ip))

    for scope, ident in keys:
        recent = session.execute(
            select(func.count())
            .select_from(AuthThrottle)
            .where(
                AuthThrottle.scope == scope,
                AuthThrottle.identifier == ident,
                AuthThrottle.created_at >= cutoff,
            )
        ).scalar_one()
        if recent >= settings.login_mail_rate_max:
            return False

    for scope, ident in keys:
        session.add(AuthThrottle(scope=scope, identifier=ident))
    session.flush()
    return True
