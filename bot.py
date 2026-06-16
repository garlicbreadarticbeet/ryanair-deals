#!/usr/bin/env python3
"""Telegram-bot (multi-user): reageert op commando's en doet onboarding via /start.

  python bot.py             -> één keer pollen en afhandelen (cron / GitHub Actions)
  python bot.py --forever   -> blijven pollen (lokaal of op de worker-host)
  python bot.py --register  -> zet het '/'-commandomenu in Telegram

De commandologica zit in app/telegram_handlers.py (testbaar). Deze module doet alleen
de Telegram-polling en het versturen. Vereist DATABASE_URL (zie .env).
"""
import sys

import requests

import notify
from app import telegram_handlers
from app.db.session import session_scope

# Korte beschrijving (max 120 tekens) — profiel & gedeelde links.
SHORT_DESC = (
    "Goedkoopste retourvluchten vanaf de vertrekvelden die jij kiest. "
    "Stel je velden + drempel in en krijg automatisch alerts."
)

# Lange beschrijving (max 512 tekens) — leeg chatvenster vóór /start.
LONG_DESC = (
    "✈️ Vindt de goedkoopste retourvluchten (heen + terug) vanaf de vertrekvelden die "
    "jij kiest, tot enkele maanden vooruit.\n\n"
    "Tik /start om te beginnen, stel je vertrekvelden in met /origins en je prijsdrempel "
    "met /drempel. Je krijgt automatisch een melding bij nieuwe deals onder je drempel.\n\n"
    "/deals voor je actuele deals, /help voor alle commando's."
)


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


def handle_update(upd):
    """Verwerk één Telegram-update: bepaal het antwoord (DB) en stuur het."""
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return
    try:
        with session_scope() as session:
            reply = telegram_handlers.handle_command(session, chat_id, text)
    except Exception as e:  # noqa: BLE001 — één kapotte update mag de bot niet stoppen
        print("handle-fout:", e)
        reply = "Er ging iets mis. Probeer het zo nog eens."
    if reply:
        send(chat_id, reply)


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
    """Zet commandomenu + korte/lange beschrijving in Telegram."""
    import json

    cmds = [
        {"command": "start", "description": "Account aanmaken of koppelen"},
        {"command": "deals", "description": "Je actuele retour-deals"},
        {"command": "origins", "description": "Vertrekvelden instellen (bv. EIN NRN)"},
        {"command": "drempel", "description": "Maximale retourprijs (€)"},
        {"command": "reisduren", "description": "Gewenste reisduren (nachten)"},
        {"command": "mij", "description": "Je huidige instellingen"},
        {"command": "stop", "description": "Account en gegevens verwijderen"},
        {"command": "help", "description": "Uitleg en commando's"},
    ]
    calls = {
        "setMyCommands": {"commands": json.dumps(cmds)},
        "setMyShortDescription": {"short_description": SHORT_DESC},
        "setMyDescription": {"description": LONG_DESC},
    }
    for method, data in calls.items():
        r = requests.post(_url(method), data=data, timeout=20).json()
        print(f"{method}: ok={r.get('ok')} {'' if r.get('ok') else r.get('description', '')}")


if __name__ == "__main__":
    if "--register" in sys.argv:
        register_commands()
    elif "--forever" in sys.argv:
        poll_forever()
    else:
        poll_once()
