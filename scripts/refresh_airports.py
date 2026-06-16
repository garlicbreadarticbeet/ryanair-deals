#!/usr/bin/env python3
"""Ververs app/db/data/airports.json vanaf Ryanair's publieke airports-endpoint.

Eenmalige/onderhouds-helper (geen runtime-afhankelijkheid). Netwerk via requests + certifi.
Draaien:  python scripts/refresh_airports.py
"""
from __future__ import annotations

import json
from pathlib import Path

import certifi
import requests

_OUT = Path(__file__).resolve().parent.parent / "app" / "db" / "data" / "airports.json"
_URL = "https://www.ryanair.com/api/views/locate/5/airports/en/active"

# NL-velden die Ryanair niet serveert maar wél gebruiker-selecteerbaar moeten blijven.
_ORIGINS = {"AMS", "EIN", "NRN", "MST", "GRQ"}
_FALLBACK = {
    "MST": {"iata": "MST", "name": "Maastricht Aachen", "country_code": "nl", "city": "Maastricht"},
    "GRQ": {"iata": "GRQ", "name": "Groningen Eelde", "country_code": "nl", "city": "Groningen"},
}


def main() -> None:
    r = requests.get(_URL, timeout=20, verify=certifi.where(),
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    out: dict[str, dict] = {}
    for a in r.json():
        iata = a["code"]
        out[iata] = {
            "iata": iata,
            "name": a["name"],
            "country_code": a["country"]["code"],
            "city": (a.get("city") or {}).get("name"),
            "is_origin_seed": iata in _ORIGINS,
        }
    for iata, fb in _FALLBACK.items():
        if iata not in out:
            out[iata] = {**fb, "is_origin_seed": True}
        else:
            out[iata]["is_origin_seed"] = True

    airports = sorted(out.values(), key=lambda x: x["iata"])
    _OUT.write_text(json.dumps(airports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Geschreven: {_OUT} ({len(airports)} luchthavens)")


if __name__ == "__main__":
    main()
