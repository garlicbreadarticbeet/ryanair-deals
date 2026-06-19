"""Travelpayouts/Aviasales-adapter — de gecachte Flight Data API als retour-native bron.

Zie DECISIONS D8 + `Vliegseintje_vluchtdata-bron_advies.md`. Bevraagt UITSLUITEND het
gecachte ``prices_for_dates``-endpoint (geautomatiseerd bevragen is daar toegestaan; de
live-search-API niet) en levert retours direct als ``ReturnFare`` — inclusief de
affiliate-boekingslink met jouw marker. De combinatie-logica van core/ wordt hier niet
gebruikt: de cache ís al een retour.

Implementeert ook (lege) ``discover_routes``/``daily_fares`` zodat de adapter het
FlightProvider-contract blijft vervullen; de scan kiest het ``return_deals``-pad.

Netwerk via requests + certifi (app.net). Geen token gezet → lege resultaten (geen fout).
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor

from app.providers.base import DailyFare, ReturnFare, Route, get_session
from app.providers.registry import register
from app.settings import settings

_API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
_BOOK_BASE = "https://www.aviasales.com"

# Leesbare maatschappijnamen voor de alert (IATA → naam); val terug op de code.
_AIRLINES = {
    "FR": "Ryanair", "RK": "Ryanair UK", "W6": "Wizz Air", "W9": "Wizz Air UK",
    "U2": "easyJet", "EC": "easyJet Europe", "HV": "Transavia", "TO": "Transavia France",
    "VY": "Vueling", "KL": "KLM", "TP": "TAP", "IB": "Iberia", "LO": "LOT", "TB": "TUI fly",
}

# Curated set populaire Ryanair/Wizz-citytrip-bestemmingen (IATA). Pragmatisch: de cache
# heeft geen schone "routes vanaf origin"-feed, dus we bevragen deze bestemmingen gericht.
# Uit te breiden/te tunen zonder de rest te raken.
_DESTINATIONS = [
    "BCN", "MAD", "AGP", "ALC", "SVQ", "VLC", "PMI", "IBZ", "SCQ",   # Spanje
    "LIS", "OPO", "FAO",                                              # Portugal
    "CIA", "BGY", "BLQ", "NAP", "VCE", "PSA", "CTA", "BRI",          # Italië
    "PRG", "BUD", "KRK", "WAW", "GDN", "WRO", "OTP", "SOF", "ZAG",   # Centraal/Oost-EU
    "VIE", "DUB", "EDI", "BVA", "MRS", "BER", "ATH", "RIX", "MLA",   # overig EU
]


@register
class TravelpayoutsProvider:
    """Adapter voor Travelpayouts (provider-code 'travelpayouts')."""

    code = "travelpayouts"

    def __init__(self) -> None:
        self._session = get_session()

    # --- FlightProvider-contract (niet gebruikt voor deze bron; bewust leeg) ---
    def discover_routes(self, origins, date_from, date_to, destination_country=None) -> Iterable[Route]:
        return []

    def daily_fares(self, origin, destination, months, currency) -> Iterable[DailyFare]:
        return []

    # --- Retour-native pad ---
    def return_deals(
        self,
        origins: Sequence[str],
        today: datetime.date,
        horizon_end: datetime.date,
        trip_lengths: Sequence[int],
        currency: str,
    ) -> Iterable[ReturnFare]:
        token = settings.travelpayouts_token
        if not token:
            return []

        market = settings.travelpayouts_market
        marker = settings.travelpayouts_marker
        cur = (currency or "EUR").lower()
        trip_set = {int(n) for n in trip_lengths}
        months = _months_between(today, horizon_end)

        tasks = [
            (o, d, month)
            for o in {o.upper() for o in origins}
            for d in _DESTINATIONS
            if d != o.upper()
            for month in months
        ]

        # Per (origin, dest, nights) de goedkoopste bewaren over alle maand-queries.
        best: dict[tuple[str, str, int], ReturnFare] = {}

        def _fetch(task) -> list[ReturnFare]:
            o, d, month = task
            out: list[ReturnFare] = []
            for rec in self._query(o, d, month, cur, market, token):
                fare = self._parse(o, d, rec, trip_set, today, horizon_end, cur, marker)
                if fare is not None:
                    out.append(fare)
            return out

        with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
            for fares in pool.map(_fetch, tasks):
                for f in fares:
                    key = (f.origin, f.destination, f.nights)
                    if key not in best or f.total < best[key].total:
                        best[key] = f
        return list(best.values())

    # --- helpers ---
    def _query(self, origin, dest, month, cur, market, token) -> list[dict]:
        """Eén gecachte round-trip-query; lege lijst bij elke fout (tolerant, zoals de scan)."""
        params = {
            "origin": origin, "destination": dest,
            "departure_at": month, "return_at": month,
            "one_way": "false", "direct": "false", "sorting": "price",
            "limit": 30, "currency": cur, "market": market, "token": token,
        }
        try:
            r = self._session.get(_API, params=params, timeout=20)
            if r.status_code != 200:
                return []
            body = r.json()
            return body.get("data", []) if body.get("success") else []
        except Exception:
            return []

    def _parse(self, origin, dest, rec, trip_set, today, horizon_end, cur, marker) -> ReturnFare | None:
        price = rec.get("price")
        dep, ret = rec.get("departure_at"), rec.get("return_at")
        if not price or not dep or not ret:
            return None
        try:
            out_date = datetime.date.fromisoformat(dep[:10])
            in_date = datetime.date.fromisoformat(ret[:10])
        except ValueError:
            return None
        nights = (in_date - out_date).days
        if nights not in trip_set or out_date < today or out_date > horizon_end:
            return None
        code = (rec.get("airline") or "").upper()
        return ReturnFare(
            provider=self.code, origin=origin, destination=dest, nights=nights,
            out_date=out_date, in_date=in_date, total=float(price), currency=cur.upper(),
            deeplink=_deeplink(rec.get("link"), marker),
            airline=_AIRLINES.get(code, code or None),
        )


def _months_between(today: datetime.date, horizon_end: datetime.date) -> list[str]:
    """'YYYY-MM'-strings van de maand van today t/m de maand van horizon_end."""
    out, y, m = [], today.year, today.month
    while (y, m) <= (horizon_end.year, horizon_end.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _deeplink(link: str | None, marker: str) -> str | None:
    """Maak van het API-`link`-pad een volledige Aviasales-boekings-URL met affiliate-marker."""
    if not link:
        return None
    sep = "&" if "?" in link else "?"
    tail = f"{sep}marker={marker}" if marker else ""
    return f"{_BOOK_BASE}{link}{tail}"
