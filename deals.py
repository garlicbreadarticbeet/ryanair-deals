#!/usr/bin/env python3
"""Ryanair retour-deal-scanner.

Toont per bestemming de goedkoopste 3-, 5- en 7-daagse retour (heen+terug),
en stuurt Telegram-alerts bij nieuwe deals onder de drempel.

  scan           -> tabel met 3/5/7-daagse retour per bestemming (+ report.md/.csv)
  watch          -> scan + Telegram-alert bij nieuwe deals onder de drempel
  test-telegram  -> stuur een testbericht
"""
import argparse
import csv
import html
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import requests
from ryanair import Ryanair

import config
from notify import send_telegram, telegram_configured

NL_MONTHS = ["", "jan", "feb", "mrt", "apr", "mei", "jun",
             "jul", "aug", "sep", "okt", "nov", "dec"]
NL_DAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
FARE_BASE = "https://services-api.ryanair.com/farfnd/v4/oneWayFares"


def fmt_day(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{d.day} {NL_MONTHS[d.month]}"


def fmt_full(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{NL_DAYS[d.weekday()]} {d.day} {NL_MONTHS[d.month]}"


def fmt_now():
    n = datetime.now()
    return f"{fmt_full(n.date())} {n:%H:%M}"


# ---------- per-dag prijzen ophalen ----------

def months_in_horizon():
    """Lijst van 'YYYY-MM-01' die de horizon (+langste reis) raakt."""
    start = date.today().replace(day=1)
    end = date.today() + timedelta(days=int(config.MONTHS_AHEAD * 30.5) + max(config.TRIP_LENGTHS))
    months, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}-01")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


def fetch_perday(session, orig, dest, months):
    """{date: (prijs, vertrek_iso)} met enkel beschikbare dagen."""
    out = {}
    for month in months:
        url = f"{FARE_BASE}/{orig}/{dest}/cheapestPerDay"
        try:
            r = session.get(url, params={"outboundMonthOfDate": month,
                                         "currency": config.CURRENCY}, timeout=20)
            if r.status_code != 200:
                continue
            fares = r.json().get("outbound", {}).get("fares", [])
        except Exception:
            continue
        for f in fares:
            p = f.get("price")
            if not p or f.get("soldOut") or f.get("unavailable"):
                continue
            try:
                d = date.fromisoformat(f["day"])
            except Exception:
                continue
            out[d] = (float(p["value"]), f.get("departureDate"))
    return out


def best_returns(outbound, inbound, today, horizon_end):
    """Voor elke reisduur de goedkoopste heen+terug-combinatie."""
    res = {}
    for n in config.TRIP_LENGTHS:
        best = None
        for d_out, (p_out, dep_out) in outbound.items():
            if d_out < today or d_out > horizon_end:
                continue
            d_in = d_out + timedelta(days=n)
            if d_in in inbound:
                p_in, dep_in = inbound[d_in]
                total = round(p_out + p_in, 2)
                if best is None or total < best["total"]:
                    best = {"total": total, "out_date": d_out.isoformat(),
                            "in_date": d_in.isoformat(),
                            "out_price": p_out, "in_price": p_in,
                            "out_dep": dep_out, "in_dep": dep_in}
        if best:
            res[n] = best
    return res


def scan(verbose=True):
    today = date.today()
    horizon_end = today + timedelta(days=int(config.MONTHS_AHEAD * 30.5))
    months = months_in_horizon()
    api = Ryanair(currency=config.CURRENCY)

    # 1) bestaande routes ontdekken per vertrekveld
    routes = []
    for origin in config.ORIGINS:
        try:
            flights = api.get_cheapest_flights(
                origin, today, horizon_end,
                destination_country=config.DESTINATION_COUNTRY)
        except Exception as e:
            if verbose:
                print(f"  ! {origin}: {e}", file=sys.stderr)
            flights = []
        seen = set()
        for f in flights:
            dest = f.destination
            if config.ONLY_DESTINATIONS and dest not in config.ONLY_DESTINATIONS:
                continue
            if dest in config.EXCLUDE_DESTINATIONS or dest in seen:
                continue
            seen.add(dest)
            routes.append((origin, f.originFull, dest, f.destinationFull))
        if verbose:
            print(f"  {origin}: {len(seen)} bestemmingen")

    if verbose:
        print(f"Per-dag prijzen ophalen voor {len(routes)} routes (heen + terug)...")

    # 2) per route per-dag prijzen ophalen en combineren
    def work(route):
        origin, origin_full, dest, dest_full = route
        session = requests.Session()
        outbound = fetch_perday(session, origin, dest, months)
        inbound = fetch_perday(session, dest, origin, months)
        by_len = best_returns(outbound, inbound, today, horizon_end)
        if not by_len:
            return None
        return (f"{origin}-{dest}", {
            "origin": origin, "originFull": origin_full,
            "destination": dest, "destinationFull": dest_full,
            "by_length": by_len,
        })

    results = {}
    with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as ex:
        for res in ex.map(work, routes):
            if res:
                results[res[0]] = res[1]
    return results


def min_total(rec):
    return min(v["total"] for v in rec["by_length"].values())


# ---------- rapporten ----------

def _cell_md(v):
    if not v:
        return "—"
    return f"€{v['total']:.2f} ({fmt_day(v['out_date'])}→{fmt_day(v['in_date'])})"


def write_reports(results):
    config.DATA_DIR.mkdir(exist_ok=True)
    recs = sorted(results.values(), key=min_total)

    lengths = config.TRIP_LENGTHS
    header = "| Bestemming | Vanaf | " + " | ".join(f"{n} dagen" for n in lengths) + " |"
    sep = "|------------|-------|" + "|".join(["---------"] * len(lengths)) + "|"
    lines = [
        "# Ryanair retour-deals — goedkoopste 3/5/7-daagse trip",
        "",
        f"_Gescand op {fmt_now()} · vanaf {', '.join(config.ORIGINS)} · "
        f"komende {config.MONTHS_AHEAD} maanden · prijs = heen+terug totaal_",
        "",
        header, sep,
    ]
    for r in recs:
        bl = r["by_length"]
        cells = " | ".join(_cell_md(bl.get(n)) for n in lengths)
        lines.append(f"| {r['destinationFull']} ({r['destination']}) | {r['origin']} | {cells} |")
    config.REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with open(config.REPORT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        cols = ["van_code", "van", "naar_code", "naar"]
        for n in lengths:
            cols += [f"{n}d_prijs", f"{n}d_heen", f"{n}d_terug"]
        w.writerow(cols)
        for r in recs:
            row = [r["origin"], r["originFull"], r["destination"], r["destinationFull"]]
            for n in lengths:
                v = r["by_length"].get(n)
                row += [f"{v['total']:.2f}", v["out_date"], v["in_date"]] if v else ["", "", ""]
            w.writerow(row)
    return recs


def _cell_term(v):
    if not v:
        return "—"
    return f"€{v['total']:>6.2f} {fmt_day(v['out_date'])}→{fmt_day(v['in_date'])}"


def print_top(recs, n=25):
    shown = recs[:n]
    lengths = config.TRIP_LENGTHS
    print(f"\nGoedkoopste retour per bestemming (top {len(shown)} van {len(recs)}) — "
          f"prijs = heen+terug:\n")
    cols = f"  {'Bestemming':<30} {'van':<4} " + " ".join(f"{str(x)+' dagen':<22}" for x in lengths)
    print(cols)
    print("  " + "-" * (len(cols) - 2))
    for r in shown:
        bl = r["by_length"]
        name = r["destinationFull"][:30]
        cells = " ".join(f"{_cell_term(bl.get(x)):<22}" for x in lengths)
        print(f"  {name:<30} {r['origin']:<4} {cells}")


# ---------- state + alerts ----------

def load_state():
    if config.STATE_FILE.exists():
        try:
            return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state):
    config.DATA_DIR.mkdir(exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                                 encoding="utf-8")


def alert_units(results):
    """Plat naar 1 eenheid per (route, reisduur): "ORIG-DEST-Nd"."""
    units = {}
    for key, r in results.items():
        for n, v in r["by_length"].items():
            units[f"{key}-{n}d"] = {
                "price": v["total"], "out_date": v["out_date"], "in_date": v["in_date"],
                "origin": r["origin"], "originFull": r["originFull"],
                "destination": r["destination"], "destinationFull": r["destinationFull"],
                "n": n,
            }
    return units


def detect_new_deals(units, state, threshold, now_iso):
    """Bepaal welke (route, reisduur) nieuw of goedkoper onder de drempel is.

    Geeft (new_deals, nieuwe_state) terug; muteert de input-state niet.
    """
    new_deals = []
    new_state = dict(state)
    for key, u in units.items():
        prev = state.get(key, {})
        price = u["price"]
        prev_alerted = prev.get("alerted_price")
        if price <= threshold:
            if prev_alerted is None or price < prev_alerted - 0.001:
                new_deals.append((u, prev_alerted))
                alerted = price
            else:
                alerted = prev_alerted
        else:
            alerted = None  # boven drempel -> reset
        new_state[key] = {"price": price, "out_date": u["out_date"],
                          "in_date": u["in_date"], "alerted_price": alerted,
                          "last_seen": now_iso}
    new_deals.sort(key=lambda t: t[0]["price"])
    return new_deals, new_state


def format_telegram(new_deals, threshold):
    head = f"✈️ <b>{len(new_deals)} nieuwe Ryanair retour-deal(s) onder €{threshold:.0f}</b>"
    parts = [head]
    # groepeer per reisduur
    by_len = {}
    for u, prev in new_deals:
        by_len.setdefault(u["n"], []).append((u, prev))
    # bekende reisduren in config-volgorde eerst, daarna eventuele rest
    ordered = list(config.TRIP_LENGTHS) + sorted(n for n in by_len if n not in config.TRIP_LENGTHS)
    for n in ordered:
        group = by_len.get(n)
        if not group:
            continue
        group.sort(key=lambda t: t[0]["price"])
        parts.append(f"\n\n<b>━━━ {n} dagen ━━━</b>")
        for u, prev in group:
            drop = f" (was €{prev:.2f})" if prev else ""
            parts.append(
                f"\n<b>€{u['price']:.2f}</b>{drop} — "
                f"{html.escape(u['originFull'])} ⇄ {html.escape(u['destinationFull'])}\n"
                f"   heen {fmt_full(u['out_date'])} · terug {fmt_full(u['in_date'])}"
            )
    return "".join(parts)


# ---------- commando's ----------

def cmd_scan(args):
    print(f"Retour-scan vanaf {', '.join(config.ORIGINS)} — komende "
          f"{config.MONTHS_AHEAD} maanden, reisduren {config.TRIP_LENGTHS} dagen ...")
    results = scan()
    if not results:
        print("Geen retourvluchten gevonden (netwerk/API?). Rapport niet bijgewerkt.")
        return
    recs = write_reports(results)
    print_top(recs, n=args.top)
    print(f"\nVolledig overzicht : {config.REPORT_MD}")
    print(f"CSV (alle routes)  : {config.REPORT_CSV}")


def cmd_watch(args):
    threshold = args.threshold if args.threshold is not None else config.ALERT_THRESHOLD
    results = scan(verbose=not args.quiet)
    if not results:
        if not args.quiet:
            print("Geen retourvluchten opgehaald (netwerk/API?). Niets bijgewerkt.")
        return
    write_reports(results)

    units = alert_units(results)
    state = load_state()
    now_iso = datetime.now().isoformat(timespec="seconds")
    new_deals, state = detect_new_deals(units, state, threshold, now_iso)
    save_state(state)

    if not new_deals:
        if not args.quiet:
            print(f"Geen nieuwe retour-deals onder €{threshold:.0f}. "
                  f"({len(units)} opties gecheckt)")
        return

    if not args.quiet:
        print(f"\n{len(new_deals)} nieuwe retour-deal(s) onder €{threshold:.0f}:")
        for u, prev in new_deals:
            drop = f" (was €{prev:.2f})" if prev else ""
            print(f"  €{u['price']:.2f}{drop}  {u['n']}d  {u['origin']}⇄{u['destination']} "
                  f"{u['destinationFull']}")

    if telegram_configured():
        ok = send_telegram(format_telegram(new_deals, threshold))
        if not args.quiet:
            print("Telegram verstuurd." if ok else "Telegram MISLUKT (check .env/token).")
    elif not args.quiet:
        print("Telegram niet geconfigureerd — overgeslagen. Run setup_telegram.py.")


def cmd_test(args):
    if not telegram_configured():
        print("Telegram niet geconfigureerd. Run setup_telegram.py.")
        sys.exit(1)
    ok = send_telegram("✅ Ryanair retour-deal-scanner: Telegram werkt!")
    print("Verstuurd." if ok else "Mislukt.")


def main():
    p = argparse.ArgumentParser(description="Ryanair retour-deal-scanner")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Toon goedkoopste 3/5/7-daagse retour per bestemming")
    s.add_argument("--top", type=int, default=25, help="aantal regels in de terminal")
    s.set_defaults(func=cmd_scan)

    w = sub.add_parser("watch", help="Scan + Telegram-alert bij nieuwe deals")
    w.add_argument("--threshold", type=float, default=None,
                   help=f"overschrijf drempel (default {config.ALERT_THRESHOLD:.0f})")
    w.add_argument("--quiet", action="store_true", help="geen terminal-output")
    w.set_defaults(func=cmd_watch)

    t = sub.add_parser("test-telegram", help="Stuur een testbericht")
    t.set_defaults(func=cmd_test)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
