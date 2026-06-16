#!/usr/bin/env python3
"""Telegram-bot: reageert op commando's.

  python bot.py             -> één keer pollen en afhandelen (cron / GitHub Actions)
  python bot.py --forever   -> blijven pollen (lokaal, bv. via launchd)
  python bot.py --register  -> zet het '/'-commandomenu in Telegram
"""
import json
import sys

import requests

import config
import deals
import notify

HELP = (
    "🤖 <b>Ryanair deal-bot</b>\n\n"
    "/deals — alle huidige retour-deals (vandaag t/m {m} maanden), per reisduur\n"
    "/help — deze uitleg\n\n"
    "Je krijgt daarnaast automatisch een melding bij nieuwe deals onder "
    "€{t:.0f} (heen+terug)."
).format(m=config.MONTHS_AHEAD, t=config.ALERT_THRESHOLD)


def _url(method):
    return f"https://api.telegram.org/bot{notify._token()}/{method}"


def send(chat_id, text, parse_mode="HTML"):
    for chunk in notify._chunks(text):
        try:
            requests.post(_url("sendMessage"), data={
                "chat_id": chat_id, "text": chunk, "parse_mode": parse_mode,
                "disable_web_page_preview": "true",
            }, timeout=30)
        except Exception as e:
            print("send-fout:", e)


def send_document(chat_id, path, caption=""):
    try:
        with open(path, "rb") as fh:
            requests.post(_url("sendDocument"),
                          data={"chat_id": chat_id, "caption": caption},
                          files={"document": fh}, timeout=60)
    except Exception as e:
        print("send_document-fout:", e)


def deals_summary(recs, top=12):
    """Korte tekst: goedkoopste retours per reisduur (top N per duur)."""
    lines = [f"✈️ <b>Actuele retour-deals</b> — vandaag t/m {config.MONTHS_AHEAD} mnd "
             f"(prijs = heen+terug)"]
    for n in config.TRIP_LENGTHS:
        items = sorted(
            ((r["by_length"][n]["total"], r, r["by_length"][n])
             for r in recs if n in r["by_length"]),
            key=lambda t: t[0])
        if not items:
            continue
        lines.append(f"\n<b>━━━ {n} dagen ━━━</b>")
        for total, r, v in items[:top]:
            lines.append(f"€{total:.2f} — {r['origin']} ⇄ {r['destinationFull']} "
                         f"({deals.fmt_day(v['out_date'])}→{deals.fmt_day(v['in_date'])})")
    lines.append(f"\n📄 Volledige lijst ({len(recs)} bestemmingen) in het bijgevoegde bestand.")
    return "\n".join(lines)


def handle_update(upd):
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return
    # alleen reageren op de geconfigureerde eigenaar (anders kan iedereen scans triggeren)
    owner = notify._chat_id()
    if owner and str(chat_id) != str(owner):
        return
    cmd = text.split()[0].lstrip("/").split("@")[0].lower()
    if cmd in ("start", "help"):
        send(chat_id, HELP)
    elif cmd == "deals":
        send(chat_id, "⏳ Even de actuele deals ophalen (~10 sec)...")
        results = deals.scan(verbose=False)
        if not results:
            send(chat_id, "Geen deals gevonden (tijdelijk API-probleem?). Probeer zo nog eens.")
            return
        recs = deals.write_reports(results)
        send(chat_id, deals_summary(recs))
        send_document(chat_id, str(config.REPORT_MD), "Alle retour-deals")
    else:
        send(chat_id, "Onbekend commando. Probeer /deals of /help.")


def get_updates(offset=None, timeout=0):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    try:
        return requests.get(_url("getUpdates"), params=params, timeout=timeout + 25).json()
    except Exception as e:
        print("getUpdates-fout:", e)
        return {"ok": False, "result": []}


def poll_once():
    data = get_updates(timeout=0)
    updates = data.get("result", [])
    for upd in updates:
        handle_update(upd)
    if updates:  # bevestig zodat verwerkte updates niet herhaald worden
        get_updates(offset=updates[-1]["update_id"] + 1, timeout=0)
    print(f"verwerkt: {len(updates)} update(s)")


def poll_forever():
    offset = None
    print("Bot luistert (Ctrl-C om te stoppen)...")
    while True:
        data = get_updates(offset=offset, timeout=30)
        for upd in data.get("result", []):
            handle_update(upd)
            offset = upd["update_id"] + 1


def register_commands():
    cmds = [
        {"command": "deals", "description": f"Alle huidige retour-deals ({config.MONTHS_AHEAD} mnd)"},
        {"command": "help", "description": "Uitleg en commando's"},
    ]
    r = requests.post(_url("setMyCommands"), data={"commands": json.dumps(cmds)}, timeout=20).json()
    print("setMyCommands ok:", r.get("ok"), r.get("description", ""))


if __name__ == "__main__":
    if "--register" in sys.argv:
        register_commands()
    elif "--forever" in sys.argv:
        poll_forever()
    else:
        poll_once()
