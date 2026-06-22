"""Gedeelde, pure opmaak-helpers voor alerts (Telegram, e-mail én de merk-dealkaart).

Eén bron van waarheid voor: stadslabel, vlag-emoji, prijs- en datumnotatie, en de
dealscore-badge ("🔥 38% onder normaal" / "laagste in 42 dagen" / "was €X"). Geen netwerk,
geen DB — alleen een AlertItem in, tekst eruit. Zo blijven de kanalen consistent en dun.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.alerts import places
from app.channels.base import AlertItem

# NL-afkortingen (locale-onafhankelijk, geen system-locale nodig).
_WEEKDAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_MONTHS = ["", "jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def flag(country_code: str | None) -> str:
    """ISO alpha-2 → vlag-emoji ('es' → 🇪🇸). Lege string bij onbekend/ongeldig.

    Alleen ASCII a–z (``isalpha`` zou ook accenten/niet-Latijn accepteren en buiten het
    regional-indicator-bereik vallen).
    """
    if not country_code or len(country_code) != 2:
        return ""
    cc = country_code.lower()
    if not all("a" <= c <= "z" for c in cc):
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("a")) for c in cc)


def safe_href(url: str | None, fallback: str = "") -> str:
    """Alleen http(s)-links toelaten in een href (geen ``javascript:``/``data:``); anders fallback."""
    if url and url.lower().startswith(("http://", "https://")):
        return url
    return fallback


def city_to(item: AlertItem) -> str:
    """Bestemmingsstad (+ vliegveld), zónder land: 'Barcelona (Reus)'. Valt terug op IATA."""
    return item.city_to or item.deal.destination


def city_from(item: AlertItem) -> str:
    return item.city_from or item.deal.origin


def country_name(item: AlertItem) -> str:
    """Bestemmingsland in het Nederlands ('Spanje'), of '' als onbekend."""
    return places.nl_country(item.country_to)


def destination_full(item: AlertItem) -> str:
    """'Barcelona (Reus), Spanje' — stad (+ vliegveld) + land, voor de tekstkanalen."""
    land = country_name(item)
    return f"{city_to(item)}, {land}" if land else city_to(item)


def route_label(item: AlertItem) -> str:
    """'Eindhoven → Barcelona (Reus), Spanje' (Nederlandse namen; valt terug op IATA-codes)."""
    return f"{city_from(item)} → {destination_full(item)}"


def money(value: float) -> str:
    """Bedrag als '€34' (heel) of '€34,50' (met centen), NL-notatie."""
    cents = round(value * 100)
    euros, rest = divmod(cents, 100)
    return f"€{euros}" if rest == 0 else f"€{euros},{rest:02d}"


def date_label(d) -> str:
    """'za 12 jul' — korte NL-datum zonder system-locale."""
    return f"{_WEEKDAYS[d.weekday()]} {d.day} {_MONTHS[d.month]}"


def dates_label(item: AlertItem) -> str:
    """'za 12 jul → di 15 jul'."""
    return f"{date_label(item.deal.out_date)} → {date_label(item.deal.in_date)}"


def nights_label(item: AlertItem) -> str:
    n = item.deal.nights
    return f"{n} nacht" if n == 1 else f"{n} nachten"


def subtitle(item: AlertItem) -> str:
    """'3 nachten · Ryanair' (airline alleen als bekend)."""
    parts = [nights_label(item)]
    if item.deal.airline:
        parts.append(item.deal.airline)
    return " · ".join(parts)


@dataclass(frozen=True)
class Badge:
    """De primaire dealscore-badge: tekst + toon ('hot' = vuur, 'good' = korting, 'info')."""

    text: str
    tone: str       # 'hot' | 'good' | 'info'

    @property
    def emoji(self) -> str:
        return {"hot": "🔥", "good": "▼", "info": "🏷️"}.get(self.tone, "")


def badge(item: AlertItem) -> Badge | None:
    """De meest overtuigende, eerlijke claim over deze prijs — of None.

    Volgorde: laagste-in-venster > sterke korting > nette korting > 'was €X' (per gebruiker).
    Nooit verzonnen urgentie; alleen wat uit de prijsgeschiedenis volgt.
    """
    s = item.score
    if s and s.has_baseline:
        if s.is_lowest:
            return Badge(f"laagste in {s.days_span} dagen", "hot")
        if s.is_strong:
            return Badge(f"{s.discount_pct}% onder normaal", "hot")
        if s.is_notable:
            return Badge(f"{s.discount_pct}% onder normaal", "good")
    if item.previous_price and item.previous_price > item.deal.total:
        return Badge(f"was {money(item.previous_price)}", "info")
    return None


def sort_key(item: AlertItem):
    """Rangschik de spannendste deals bovenaan: sterkste dealscore eerst, dan goedkoopste."""
    strength = item.score.strength if item.score else 0.0
    return (-strength, item.deal.total)
