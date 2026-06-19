"""Publieke marketingpagina's + content-routes (websiteplan §8–§10).

Server-rendered via dezelfde Jinja-templating als de app-pagina's. Alle routes geven de
ingelogde gebruiker (optioneel) mee zodat de navbar/CTA's zich aanpassen, plus ``settings``
voor merk/SEO. Bevat ook /contact (met honeypot + rate-limit), robots.txt en sitemap.xml.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.channels.email import send_email
from app.db.models import ContactMessage
from app.settings import settings
from app.web import content_store as content
from app.web.deps import get_db, optional_web_user
from app.web.templating import render

router = APIRouter()


def _canonical(path: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}{path}"


def _ctx(user, path: str, **extra) -> dict:
    """Gedeelde template-context: user + settings + canonical + paginaspecifiek."""
    return {"user": user, "settings": settings, "canonical": _canonical(path), **extra}


# ---------- statische marketingpagina's ----------

@router.get("/hoe-het-werkt", response_class=HTMLResponse)
def how_it_works(user=Depends(optional_web_user)):
    return render("hoe-het-werkt.html", **_ctx(user, "/hoe-het-werkt"))


@router.get("/premium", response_class=HTMLResponse)
def premium(user=Depends(optional_web_user)):
    return render("premium.html", **_ctx(
        user, "/premium",
        free_max_origins=settings.free_max_origins,
        pricing=settings.premium_pricing,
        instant_premium=("mode:instant" in settings.premium_only_feature_set),
    ))


@router.get("/over-ons", response_class=HTMLResponse)
def about(user=Depends(optional_web_user)):
    return render("over-ons.html", **_ctx(user, "/over-ons"))


@router.get("/bestemmingen", response_class=HTMLResponse)
def destinations(user=Depends(optional_web_user), origin: str | None = None):
    items = content.destinations()
    origins = sorted({d["origin"] for d in items})
    active = origin.upper() if origin else None
    if active:
        items = [d for d in items if d["origin"] == active]
    return render("bestemmingen.html", **_ctx(
        user, "/bestemmingen", deals=items, origins=origins, active_origin=active,
        origin_names=content.ORIGIN_NAMES,
    ))


# ---------- FAQ ----------

@router.get("/faq", response_class=HTMLResponse)
def faq(user=Depends(optional_web_user)):
    return render("faq.html", **_ctx(user, "/faq", groups=content.faq_groups()))


# ---------- blog ----------

@router.get("/blog", response_class=HTMLResponse)
def blog_index(user=Depends(optional_web_user)):
    return render("blog_index.html", **_ctx(user, "/blog", posts=content.blog_index()))


@router.get("/blog/{slug}", response_class=HTMLResponse)
def blog_post(slug: str, user=Depends(optional_web_user)):
    post = content.blog_post(slug)
    if post is None:
        return render(
            "message.html", status_code=404, user=user, settings=settings,
            heading="Artikel niet gevonden",
            message="Dit blogartikel bestaat niet (meer).",
            link="/blog", link_label="Naar de blog",
        )
    return render("blog_post.html", **_ctx(user, f"/blog/{slug}", post=post))


# ---------- legal (placeholders) ----------

@router.get("/privacy", response_class=HTMLResponse)
def privacy(user=Depends(optional_web_user)):
    return _legal(user, "privacy", "/privacy")


@router.get("/voorwaarden", response_class=HTMLResponse)
def terms(user=Depends(optional_web_user)):
    return _legal(user, "voorwaarden", "/voorwaarden")


@router.get("/cookies", response_class=HTMLResponse)
def cookies(user=Depends(optional_web_user)):
    return _legal(user, "cookies", "/cookies")


def _legal(user, slug: str, path: str) -> HTMLResponse:
    doc = content.legal_doc(slug)
    if doc is None:
        return render("message.html", status_code=404, user=user, settings=settings,
                      heading="Pagina niet gevonden", message="Deze pagina bestaat niet.",
                      link="/", link_label="Naar home")
    return render("legal.html", **_ctx(user, path, title=doc["title"], body=doc["html"]))


# ---------- contact (honeypot + eenvoudige rate-limit) ----------

_RATE: dict[str, list[float]] = {}
_RATE_WINDOW = 600.0   # 10 minuten
_RATE_MAX = 3          # max 3 berichten per IP per venster


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _RATE.get(ip, []) if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_MAX:
        _RATE[ip] = hits
        return False
    hits.append(now)
    _RATE[ip] = hits
    return True


@router.get("/contact", response_class=HTMLResponse)
def contact_form(user=Depends(optional_web_user)):
    return render("contact.html", **_ctx(user, "/contact"))


@router.post("/contact", response_class=HTMLResponse)
def contact_submit(
    request: Request,
    user=Depends(optional_web_user),
    db: Session = Depends(get_db),
    name: str = Form(""),
    email: str = Form(""),
    message: str = Form(""),
    company: str = Form(""),   # honeypot: moet leeg blijven
):
    ctx = _ctx(user, "/contact")
    # Honeypot ingevuld → stilletjes "ok" doen (bot afwimpelen), niets opslaan.
    if company.strip():
        return render("contact.html", **ctx, sent=True)

    name, email, message = name.strip(), email.strip(), message.strip()
    if not name or "@" not in email or len(message) < 5:
        return render("contact.html", status_code=400, **ctx,
                      error="Vul je naam, een geldig e-mailadres en een bericht in.",
                      form={"name": name, "email": email, "message": message})

    ip = request.client.host if request.client else "?"
    if not _rate_ok(ip):
        return render("contact.html", status_code=429, **ctx,
                      error="Je hebt net al een bericht gestuurd. Probeer het zo nog eens.",
                      form={"name": name, "email": email, "message": message})

    db.add(ContactMessage(name=name[:128], email=email[:254], message=message[:4000]))
    db.flush()

    recipient = settings.support_email or settings.resend_from
    if recipient:
        send_email(
            recipient,
            f"Nieuw contactbericht via {settings.brand_name}",
            f"<p><strong>Van:</strong> {name} &lt;{email}&gt;</p>"
            f"<p>{message}</p>",
        )
    return render("contact.html", **ctx, sent=True)


# ---------- robots.txt + sitemap.xml (SEO, §19) ----------

@router.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    base = settings.app_base_url.rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /dashboard\n"
        "Disallow: /preferences\n"
        "Disallow: /channels\n"
        "Disallow: /account\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
def sitemap() -> Response:
    paths = [
        "/", "/hoe-het-werkt", "/premium", "/bestemmingen", "/over-ons",
        "/faq", "/contact", "/blog", "/privacy", "/voorwaarden", "/cookies",
    ]
    paths += [f"/blog/{p.slug}" for p in content.blog_index()]
    urls = "".join(f"<url><loc>{_canonical(p)}</loc></url>" for p in paths)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
