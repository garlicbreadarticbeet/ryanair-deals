"""Server-rendered website (HTML). Gebruikt de service-laag (accounts, billing) direct
en cookie-sessies voor auth. De JSON-API in main.py blijft daarnaast bestaan.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.settings import settings
from app.web.deps import clear_session_cookie, optional_web_user
from app.web.templating import render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def landing(user=Depends(optional_web_user)):
    return render("index.html", user=user, settings=settings)


@router.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response
