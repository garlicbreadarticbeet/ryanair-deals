"""EmailNotifier — transactionele e-mail via de Resend-API (requests + certifi).

Levert de magic-link-mail (send_email) én de gebrande deal-alert: een responsive, email-veilige
HTML-mail (tabellen + inline CSS) in de Vliegseintje-stijl, met per deal een kaart, de prijs,
de dealscore-badge en een duidelijke boekknop. De content komt uit de gedeelde render-laag.
"""
from __future__ import annotations

import html

from app.alerts import render as R
from app.channels.base import AlertItem, register_notifier
from app.net import get_session
from app.settings import settings

_RESEND_URL = "https://api.resend.com/emails"

# Merk-tokens (uit static/style.css; e-mail kan geen CSS-variabelen, dus inline hexwaarden).
_BLUE = "#2563EB"
_INK = "#102A43"
_BODY = "#334E68"
_MUTED = "#5C748D"
_SURFACE = "#F5F8FC"
_BORDER = "#E3E9F2"
_AMBER = "#FFB703"
_BLUE_SOFT = "#BFD4FB"
_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif"
_BADGE = {
    "hot": ("#FFF4D6", "#8A5A00"),
    "good": ("#E6F6EF", "#0B6B48"),
    "info": ("#E8F0FE", "#1D4FD7"),
}


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Verstuur één transactionele e-mail via Resend. False als niet geconfigureerd/fout."""
    if not settings.resend_api_key:
        return False
    try:
        resp = get_session().post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.resend_from, "to": [to], "subject": subject, "html": html_body},
            timeout=20,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def _badge_html(it: AlertItem) -> str:
    b = R.badge(it)
    if not b:
        return ""
    bg, fg = _BADGE.get(b.tone, _BADGE["info"])
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};font:700 13px {_FONT};'
        f'padding:4px 11px;border-radius:999px;white-space:nowrap;">'
        f"{b.emoji} {html.escape(b.text)}</span>"
    )


def _cta_html(it: AlertItem) -> str:
    safe = R.safe_href(it.deal.deeplink)
    if safe:
        href, label = html.escape(safe, quote=True), "Bekijk de vlucht →"
        bg, fg = _AMBER, _INK
    else:
        href, label = f"{settings.app_base_url}/dashboard", "Bekijk op je dashboard →"
        bg, fg = _SURFACE, _BLUE
    return (
        f'<a href="{href}" style="display:block;margin-top:14px;background:{bg};color:{fg};'
        f'text-decoration:none;font:700 15px {_FONT};text-align:center;padding:13px;'
        f'border-radius:10px;">{label}</a>'
    )


def _card_html(it: AlertItem) -> str:
    d = it.deal
    airline = f" · {html.escape(d.airline)}" if d.airline else ""
    badge = _badge_html(it)
    badge_row = f'<div style="margin-top:8px;">{badge}</div>' if badge else ""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#ffffff;border:1px solid {_BORDER};border-radius:14px;margin:0 0 14px;">'
        f'<tr><td style="padding:18px 20px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td valign="top" style="font:800 30px {_FONT};color:{_INK};white-space:nowrap;">'
        f"{R.money(d.total)}</td>"
        f'<td valign="top" align="right">'
        f'<div style="font:700 18px {_FONT};color:{_INK};">'
        f"{R.flag(it.country_to)} {html.escape(R.destination_full(it))}</div>"
        f'<div style="font:400 14px {_FONT};color:{_MUTED};margin-top:3px;">'
        f"vanaf {html.escape(R.city_from(it))} · {R.nights_label(it)}{airline}</div>"
        f'<div style="font:400 14px {_FONT};color:{_MUTED};">{R.dates_label(it)}</div>'
        f"</td></tr></table>"
        f"{badge_row}"
        f"{_cta_html(it)}"
        f"</td></tr></table>"
    )


def _subject(items: list[AlertItem]) -> str:
    best = items[0]
    price = R.money(best.deal.total)
    if len(items) == 1:
        return f"✈️ {R.city_to(best)} retour voor {price}"
    return f"✈️ {R.city_to(best)} {price} + {len(items) - 1} andere deals onder je drempel"


def _hero_html(it: AlertItem) -> str:
    """Gebrande hero-afbeelding (gelinkt naar de boeking) voor de beste deal — als geconfigureerd."""
    from app.alerts.card import signed_card_url

    url = signed_card_url(it)
    if not url:
        return ""
    href = html.escape(R.safe_href(it.deal.deeplink, f"{settings.app_base_url}/dashboard"), quote=True)
    alt = f"{R.city_to(it)} {R.money(it.deal.total)}"
    img = (
        f'<a href="{href}"><img src="{html.escape(url, quote=True)}" width="600" '
        f'alt="{html.escape(alt)}" style="display:block;width:100%;max-width:600px;'
        f'border:0;border-radius:14px;"></a>'
    )
    return f'<tr><td style="padding:0 0 14px;">{img}{_cta_html(it)}</td></tr>'


def _email_shell(rows_html: str, *, intro: str | None = None, footer_html: str | None = None) -> str:
    """Gebrande, email-veilige wrapper (header + content-rijen + footer) in de Vliegseintje-stijl.

    ``rows_html`` zijn ``<tr>``-rijen die direct in de 600px-tabel komen (zo blijft de
    deal-hero, die zelf een rij is, geldig). Gedeeld door de deal-alerts én de inlogmail.
    """
    intro_row = (
        f'<div style="font:400 14px {_FONT};color:{_BLUE_SOFT};margin-top:4px;">{html.escape(intro)}</div>'
        if intro else ""
    )
    footer = footer_html or f"{html.escape(settings.brand_name)} · {html.escape(settings.brand_tagline)}"
    return (
        f'<div style="background:{_SURFACE};padding:24px 0;font-family:{_FONT};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:92%;">'
        f'<tr><td style="background:{_BLUE};border-radius:14px;padding:22px 24px;">'
        f'<div style="font:800 22px {_FONT};color:#ffffff;">✈️ {html.escape(settings.brand_name)}</div>'
        f"{intro_row}</td></tr>"
        f'<tr><td style="height:18px;line-height:18px;">&nbsp;</td></tr>'
        f"{rows_html}"
        f'<tr><td style="padding:14px 8px 0;">'
        f'<p style="font:400 12px {_FONT};color:{_MUTED};text-align:center;line-height:1.6;">{footer}</p>'
        f"</td></tr></table></td></tr></table></div>"
    )


def _render(items: list[AlertItem]) -> tuple[str, str]:
    n = len(items)
    intro = f"Je seintje is binnen — {n} {'deal' if n == 1 else 'deals'} onder je drempel."
    hero = _hero_html(items[0])
    rest = items[1:] if hero else items   # hero vervangt de eerste kaart (geen dubbele beste deal)
    cards = "".join(_card_html(it) for it in rest)
    footer = (
        "Prijzen zijn indicatief en kunnen wijzigen; je boekt zelf bij de airline.<br>"
        f'<a href="{settings.app_base_url}/preferences" style="color:{_MUTED};">Voorkeuren aanpassen</a> · '
        f'<a href="{settings.app_base_url}/account" style="color:{_MUTED};">Afmelden</a>'
    )
    body = _email_shell(f"{hero}<tr><td>{cards}</td></tr>", intro=intro, footer_html=footer)
    return _subject(items), body


def _login_email(link: str) -> tuple[str, str]:
    """Gebrande inlogmail (magic-link): één duidelijke knop + fallback-link + veiligheidsnoot."""
    safe = html.escape(link, quote=True)
    inner = (
        f'<tr><td style="background:#ffffff;border:1px solid {_BORDER};border-radius:16px;padding:30px 28px;">'
        f'<div style="font:700 22px {_FONT};color:{_INK};">Log in bij {html.escape(settings.brand_name)}</div>'
        f'<p style="font:400 15px {_FONT};color:{_BODY};margin:10px 0 22px;">Klik op de knop om in te loggen '
        f"en je e-mailadres te bevestigen. Je hebt geen wachtwoord nodig.</p>"
        f'<a href="{safe}" style="display:inline-block;background:{_AMBER};color:{_INK};text-decoration:none;'
        f'font:700 16px {_FONT};padding:14px 30px;border-radius:10px;">Log in →</a>'
        f'<p style="font:400 13px {_FONT};color:{_MUTED};margin:22px 0 0;">Werkt de knop niet? Plak deze link '
        f'in je browser:<br><a href="{safe}" style="color:{_BLUE};word-break:break-all;">{safe}</a></p>'
        f'<p style="font:400 12px {_FONT};color:{_MUTED};margin:14px 0 0;">Deze link is eenmalig en verloopt na '
        f"korte tijd. Heb je dit niet aangevraagd? Dan kun je deze mail negeren.</p>"
        f"</td></tr>"
    )
    return f"Je inloglink voor {settings.brand_name}", _email_shell(inner)


def send_login_email(to: str, link: str) -> bool:
    """Bouw + verstuur de gebrande inlogmail (magic-link)."""
    subject, body = _login_email(link)
    return send_email(to, subject, body)


@register_notifier
class EmailNotifier:
    channel_type = "email"

    def send(self, address: str, items: list[AlertItem]) -> bool:
        if not items:
            return True
        subject, body = _render(items)
        return send_email(address, subject, body)
