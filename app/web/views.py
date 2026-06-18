"""Server-rendered website (HTML). Gebruikt de service-laag (accounts, billing) direct
en cookie-sessies voor auth. De JSON-API in main.py blijft daarnaast bestaan.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import accounts
from app.channels.email import send_email
from app.settings import settings
from app.web.deps import (
    clear_session_cookie,
    get_db,
    optional_web_user,
    set_session_cookie,
)
from app.web.templating import render

router = APIRouter()


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
