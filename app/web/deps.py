"""Gedeelde FastAPI-dependencies: DB-sessie, API-Bearer-auth en web-cookie-auth."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import SessionLocal
from app.web import auth

COOKIE_NAME = "gv_session"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 dagen


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
    """API-auth via 'Authorization: Bearer <sessietoken>'."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="ontbrekend sessietoken")
    user_id = auth.verify_session(db, authorization.split(" ", 1)[1])
    if user_id is None:
        raise HTTPException(status_code=401, detail="ongeldig of verlopen token")
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="geen actief account")
    return user


def optional_web_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Web-auth via session-cookie; None als niet (geldig) ingelogd."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = auth.verify_session(db, token)
    if user_id is None:
        return None
    user = db.get(User, user_id)
    return user if user is not None and user.status == "active" else None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", max_age=_COOKIE_MAX_AGE, path="/"
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
