"""Merk-dealkaart — een gebrande PNG voor de Telegram-foto en de e-mail-hero.

Getekend met Pillow op de Vliegseintje-merkkleuren en -fonts (self-hosted, als TTF gebundeld
onder assets/fonts/). Geen emoji in het beeld (Latijnse fonts) — de "punch" komt van kleur,
de grote prijs en de amber dealscore-pill. Faalt nooit hard: kan Pillow/fonts niet laden, dan
geeft ``render_deal_card`` ``None`` terug en valt het kanaal terug op tekst/HTML zonder beeld.
"""
from __future__ import annotations

import hashlib
import hmac
import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

from app.alerts import render as R
from app.channels.base import AlertItem
from app.settings import settings

try:  # Pillow is optioneel: zonder de lib (of fonts) geen kaart, maar wel gewoon alerts.
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except Exception:  # noqa: BLE001
    _PIL_OK = False

_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# Merkkleuren (RGB).
_INK = (16, 42, 67)
_BODY = (51, 78, 104)
_MUTED = (92, 116, 141)
_BLUE = (37, 99, 235)
_BLUE_SOFT = (191, 212, 251)
_AMBER = (255, 183, 3)
_WHITE = (255, 255, 255)
_SURFACE = (245, 248, 252)
_BADGE_RGB = {
    "hot": ((255, 183, 3), _INK),          # amber-pill, donkere tekst
    "good": ((230, 246, 239), (11, 107, 72)),
    "info": ((232, 240, 254), (29, 79, 215)),
}

_W, _H = 1200, 628
_PAD = 64


@dataclass(frozen=True)
class CardData:
    price: str
    city_to: str
    city_from: str
    subtitle: str
    dates: str
    badge_text: str | None
    badge_tone: str | None


def build_card_data(item: AlertItem) -> CardData:
    """Display-velden voor de kaart uit een AlertItem (deelt de gedeelde render-helpers)."""
    b = R.badge(item)
    # En-dash i.p.v. de '→' uit dates_label: de gesubsette merk-TTF heeft geen pijl-glyph
    # (op de site vangt de systeemfont dat op; Pillow heeft die fallback niet).
    dates = f"{R.date_label(item.deal.out_date)} – {R.date_label(item.deal.in_date)}"
    # Hero = stad (+ vliegveld) kort; het land staat in de subtitel (anders te lang voor de hero).
    sub = " · ".join(p for p in (R.country_name(item), R.nights_label(item), item.deal.airline) if p)
    return CardData(
        price=R.money(item.deal.total),
        city_to=R.city_to(item),
        city_from=R.city_from(item),
        subtitle=sub,
        dates=dates,
        badge_text=b.text if b else None,
        badge_tone=b.tone if b else None,
    )


@lru_cache(maxsize=1)
def _fonts() -> dict | None:
    """Laad de gebundelde merk-TTF's één keer; None als ze ontbreken (→ geen kaart)."""
    if not _PIL_OK:
        return None
    try:
        return {
            "price": ImageFont.truetype(str(_FONT_DIR / "poppins-700.ttf"), 150),
            "city": ImageFont.truetype(str(_FONT_DIR / "poppins-700.ttf"), 66),
            "wordmark": ImageFont.truetype(str(_FONT_DIR / "poppins-700.ttf"), 34),
            "badge": ImageFont.truetype(str(_FONT_DIR / "inter-600.ttf"), 30),
            "body": ImageFont.truetype(str(_FONT_DIR / "inter-400.ttf"), 31),
        }
    except Exception:  # noqa: BLE001
        return None


def _logo_mark(draw, x: int, y: int, size: int = 52) -> None:
    """Merk-mark (variant A): blauw afgerond vierkant + wit vliegtuigje + amber ping aan de neus."""
    s = size
    draw.rounded_rectangle([x, y, x + s, y + s], radius=round(s * 0.25), fill=_BLUE)
    # Vliegtuigje: witte bovenkant + lichtblauwe vouw (zelfde geometrie als het SVG-logo).
    nose = (x + 0.760 * s, y + 0.240 * s)
    draw.polygon([(x + 0.240 * s, y + 0.422 * s), nose, (x + 0.474 * s, y + 0.526 * s)], fill=_WHITE)
    draw.polygon([nose, (x + 0.578 * s, y + 0.760 * s), (x + 0.474 * s, y + 0.526 * s)], fill=_BLUE_SOFT)
    # Amber ping aan de neus (met dunne blauwe rand zodat 'ie loskomt van het witte vliegtuig).
    r = 0.092 * s
    draw.ellipse([nose[0] - r, nose[1] - r, nose[0] + r, nose[1] + r],
                 fill=_AMBER, outline=_BLUE, width=max(1, round(s * 0.03)))


def _truncate(draw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def render_card(data: CardData) -> bytes | None:
    """Render één merk-dealkaart naar PNG-bytes, of None als rendering niet beschikbaar is."""
    fonts = _fonts()
    if fonts is None:
        return None
    try:
        img = Image.new("RGB", (_W, _H), _WHITE)
        d = ImageDraw.Draw(img)

        # Decoratieve amber 'ping' (concentrische cirkels) rechtsboven — het seintje-motief.
        for rr, col in ((220, _SURFACE), (150, (255, 244, 214)), (80, (255, 236, 179))):
            d.ellipse([_W - rr, -rr, _W + rr, rr], fill=col)

        # Header: merk-mark + wordmark.
        _logo_mark(d, _PAD, 52, 52)
        d.text((_PAD + 68, 60), "Vliegseintje", font=fonts["wordmark"], fill=_BLUE)

        # Bestemming (hero) + de grote prijs.
        d.text((_PAD, 168), _truncate(d, data.city_to, fonts["city"], _W - 2 * _PAD), font=fonts["city"], fill=_BODY)
        d.text((_PAD, 232), data.price, font=fonts["price"], fill=_INK)

        # Details.
        d.text((_PAD, 432), _truncate(d, f"vanaf {data.city_from} · {data.subtitle}", fonts["body"], _W - 2 * _PAD),
               font=fonts["body"], fill=_MUTED)
        d.text((_PAD, 478), data.dates, font=fonts["body"], fill=_MUTED)

        # Dealscore-pill.
        if data.badge_text:
            bg, fg = _BADGE_RGB.get(data.badge_tone or "info", _BADGE_RGB["info"])
            tw = d.textlength(data.badge_text, font=fonts["badge"])
            x0, y0 = _PAD, 540
            x1, y1 = int(x0 + tw + 44), y0 + 52
            d.rounded_rectangle([x0, y0, x1, y1], radius=26, fill=bg)
            d.text((x0 + 22, y0 + 10), data.badge_text, font=fonts["badge"], fill=fg)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


def render_deal_card(item: AlertItem) -> bytes | None:
    """Gemak: bouw de display-data en render de kaart voor één deal."""
    return render_card(build_card_data(item))


# ---------- ondertekende /cards-URL (voor de mail-hero) ----------
# De display-velden gaan als querystring mee en worden HMAC-ondertekend met
# ``alert_card_secret`` zodat alleen door ons uitgegeven kaarten gerenderd worden (geen
# kaarten met willekeurige tekst). Telegram heeft dit niet nodig (bytes-upload).

_PARAM_KEYS = ("price", "city_to", "city_from", "subtitle", "dates", "badge_text", "badge_tone")


def _canonical_qs(params: dict) -> str:
    return urlencode([(k, params.get(k) or "") for k in _PARAM_KEYS])


def _sign(qs: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256).hexdigest()


def _params_of(data: CardData) -> dict:
    return {
        "price": data.price, "city_to": data.city_to, "city_from": data.city_from,
        "subtitle": data.subtitle, "dates": data.dates,
        "badge_text": data.badge_text or "", "badge_tone": data.badge_tone or "",
    }


def signed_card_url(item: AlertItem) -> str | None:
    """Ondertekende absolute URL naar de kaart van deze deal, of None (geen secret/base-url)."""
    secret, base = settings.alert_card_secret, settings.app_base_url
    if not (secret and base):
        return None
    qs = _canonical_qs(_params_of(build_card_data(item)))
    return f"{base.rstrip('/')}/cards/deal.png?{qs}&sig={_sign(qs, secret)}"


def render_card_from_params(params: dict, sig: str | None) -> bytes | None:
    """Verifieer de handtekening en render de kaart uit de querystring-velden (None bij mismatch)."""
    secret = settings.alert_card_secret
    if not secret:
        return None
    expected = _sign(_canonical_qs(params), secret)
    try:
        if not hmac.compare_digest(expected.encode("ascii"), (sig or "").encode("utf-8")):
            return None
    except (UnicodeEncodeError, ValueError):
        return None
    return render_card(CardData(
        price=params.get("price", ""), city_to=params.get("city_to", ""),
        city_from=params.get("city_from", ""), subtitle=params.get("subtitle", ""),
        dates=params.get("dates", ""), badge_text=params.get("badge_text") or None,
        badge_tone=params.get("badge_tone") or None,
    ))
