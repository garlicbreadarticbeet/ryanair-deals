"""Route-test voor de Travelpayouts cached Data API (zie DECISIONS D8 + het onderzoek).

Beantwoordt de checklist-vraag uit `Vliegseintje_vluchtdata-bron_advies.md`:
  (a) is er überhaupt data voor ONZE routes (EIN/NRN/BRU/CRL/AMS)?
  (b) hoe vers is die (cached) data?
  (c) komen Ryanair (FR) en Wizz (W6/W9) erin voor?
  (d) waar landt de affiliate-`link`?

Het is een DEV/OPS-probe (geen runtime-code) en raakt de scan-engine niet. Bevragen gebeurt op het
*cached* `prices_for_dates`-endpoint — het enige dat geautomatiseerd bevragen toestaat.

Gebruik:
    TRAVELPAYOUTS_TOKEN=xxxx TRAVELPAYOUTS_MARKER=12345 \
        .venv/bin/python -m scripts.probe_travelpayouts            # standaard: komende maand
    .venv/bin/python -m scripts.probe_travelpayouts --months 2 --limit 30
    .venv/bin/python -m scripts.probe_travelpayouts --token xxx --market be

Token + marker haal je gratis op travelpayouts.com (Profiel -> API token / Partner-marker).
"""
from __future__ import annotations

import argparse
import datetime
from collections import Counter

from app.net import get_session
from app.settings import settings

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
BOOK_BASE = "https://www.aviasales.com"

# Vertrekvelden + een representatieve set Ryanair/Wizz-bestemmingen (IATA).
ORIGINS = ["EIN", "NRN", "BRU", "CRL", "AMS"]
DESTINATIONS = ["BCN", "LIS", "OPO", "PRG", "BUD", "VIE", "KRK", "AGP", "ALC", "FAO"]

# IATA-airlinecode -> leesbare naam (voor het herkennen van prijsvechters).
AIRLINES = {
    "FR": "Ryanair", "RK": "Ryanair UK", "W6": "Wizz Air", "W9": "Wizz Air UK",
    "U2": "easyJet", "EC": "easyJet Europe", "HV": "Transavia", "TO": "Transavia France",
    "VY": "Vueling", "KL": "KLM", "TB": "TUI fly",
}


def _next_months(n: int) -> list[str]:
    today = datetime.date.today()
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _query(session, token, market, origin, dest, month, limit):
    """Eén cached round-trip-zoek; geeft (records, foutmelding-of-None) terug."""
    params = {
        "origin": origin, "destination": dest,
        "departure_at": month, "return_at": month,
        "unique": "false", "sorting": "price", "direct": "false",
        "currency": "eur", "limit": limit, "one_way": "false",
        "market": market, "token": token,
    }
    try:
        r = session.get(API, params=params, timeout=20)
    except Exception as exc:  # noqa: BLE001
        return [], f"netwerkfout: {exc}"
    if r.status_code != 200:
        return [], f"HTTP {r.status_code}: {r.text[:120]}"
    body = r.json()
    if not body.get("success", False):
        return [], f"API-fout: {body.get('error') or body}"
    return body.get("data", []) or [], None


def main() -> None:
    ap = argparse.ArgumentParser(description="Travelpayouts route-test (cached Data API)")
    ap.add_argument("--token", default=settings.travelpayouts_token)
    ap.add_argument("--marker", default=settings.travelpayouts_marker)
    ap.add_argument("--market", default=settings.travelpayouts_market)
    ap.add_argument("--months", type=int, default=1, help="aantal komende maanden (default 1)")
    ap.add_argument("--limit", type=int, default=30, help="max records per route-maand")
    args = ap.parse_args()

    if not args.token:
        print("Geen token. Zet TRAVELPAYOUTS_TOKEN in .env of geef --token mee.\n"
              "Gratis ophalen op travelpayouts.com (Profiel -> API token).")
        return

    session = get_session()
    months = _next_months(args.months)
    print(f"Travelpayouts cached Data API — markt={args.market}, maanden={', '.join(months)}\n")

    airline_counter: Counter[str] = Counter()
    routes_with_data = 0
    routes_total = 0
    sample_link = None
    fresh_seen = False

    for origin in ORIGINS:
        print(f"── {origin} " + "─" * 56)
        for dest in DESTINATIONS:
            routes_total += 1
            best = None
            err = None
            for month in months:
                recs, e = _query(session, args.token, args.market, origin, dest, month, args.limit)
                if e:
                    err = e
                    continue
                for rec in recs:
                    price = rec.get("price")
                    if price is None:
                        continue
                    if best is None or price < best.get("price", 1e9):
                        best = rec
            if best is None:
                print(f"  {origin}→{dest}:  —  ({err or 'geen data'})")
                continue
            routes_with_data += 1
            code = (best.get("airline") or "?").upper()
            airline_counter[code] += 1
            name = AIRLINES.get(code, code)
            link = best.get("link", "")
            if link and sample_link is None:
                sep = "&" if "?" in link else "?"
                sample_link = f"{BOOK_BASE}{link}{sep}marker={args.marker or 'JOUW_MARKER'}"
            fresh = best.get("expires_at") or best.get("found_at") or ""
            if fresh:
                fresh_seen = True
            print(f"  {origin}→{dest}:  €{best.get('price')} retour · {name} "
                  f"· heen {best.get('departure_at','?')[:10]} · terug {best.get('return_at','?')[:10]}"
                  f"{(' · vers tot ' + fresh[:19]) if fresh else ''}")

    print("\n" + "═" * 64)
    cov = (routes_with_data / routes_total * 100) if routes_total else 0
    print(f"DEKKING: {routes_with_data}/{routes_total} routes met data ({cov:.0f}%)")
    if airline_counter:
        tops = ", ".join(f"{AIRLINES.get(c, c)} ({n})" for c, n in airline_counter.most_common())
        print(f"AIRLINES: {tops}")
        has_fr = airline_counter.get("FR", 0) + airline_counter.get("RK", 0)
        has_wizz = airline_counter.get("W6", 0) + airline_counter.get("W9", 0)
        print(f"  → Ryanair-resultaten: {has_fr} · Wizz-resultaten: {has_wizz}")
    print(f"VERSHEID: {'expires_at/found_at aanwezig in respons' if fresh_seen else 'geen versheidsveld gezien — handmatig checken'}")
    if sample_link:
        print(f"VOORBEELD-LINK (waar landt de boeking?):\n  {sample_link}")
    print("\nLet op: dit is cached/indicatieve data. Beoordeel of dekking + versheid genoeg zijn\n"
          "vóór we de definitieve adapter erop bouwen (zie checklist in het onderzoek).")


if __name__ == "__main__":
    main()
