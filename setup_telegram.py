#!/usr/bin/env python3
"""Helper: vind je Telegram chat-id en schrijf token + chat-id naar .env.

Vooraf:
  1) Open Telegram, start een chat met @BotFather, stuur /newbot en volg de stappen.
  2) Je krijgt een token (bv. 123456789:ABC...). Plak die hieronder.
  3) Open je nieuwe bot en stuur 'm een bericht (druk op START of typ /start).
Daarna dit script draaien:  .venv/bin/python setup_telegram.py
"""
import os
import sys
from pathlib import Path

import requests

ENV = Path(__file__).resolve().parent / ".env"
API = "https://api.telegram.org/bot{token}/{method}"


def call(token, method, **params):
    return requests.get(API.format(token=token, method=method),
                        params=params, timeout=20).json()


def read_env():
    d = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def write_env(d):
    ENV.write_text("\n".join(f"{k}={v}" for k, v in d.items()) + "\n", encoding="utf-8")


def collect_chats(updates):
    chats = {}
    for upd in updates.get("result", []):
        msg = (upd.get("message") or upd.get("edited_message")
               or upd.get("channel_post") or {})
        chat = msg.get("chat") or (upd.get("my_chat_member") or {}).get("chat")
        if chat:
            chats[chat["id"]] = (chat.get("first_name") or chat.get("title")
                                 or chat.get("username") or "")
    return chats


def main():
    env = read_env()
    token = (env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        token = input("Plak je bot-token (van @BotFather): ").strip()
    if not token:
        print("Geen token opgegeven. Stop.")
        sys.exit(1)

    # 1) Token geldig? En welke bot is het?
    me = call(token, "getMe")
    if not me.get("ok"):
        print("❌ Token werkt niet:", me.get("description", me))
        print("   Check of je de héle token kopieerde (vorm: 123456789:AA...).")
        sys.exit(1)
    uname = me["result"].get("username", "?")
    print(f"✅ Token OK — dit is bot @{uname}")
    print(f"   Schrijf je /start naar PRECIES deze bot? -> https://t.me/{uname}")

    # 2) Staat er een webhook? Die blokkeert getUpdates.
    wh = call(token, "getWebhookInfo")
    if wh.get("ok") and wh["result"].get("url"):
        print(f"⚠️  Er staat een webhook ({wh['result']['url']}); getUpdates werkt dan niet.")
        call(token, "deleteWebhook")
        print("   Webhook verwijderd.")

    # 3) Updates ophalen (met paar retries)
    updates = {}
    chats = {}
    for attempt in range(1, 6):
        updates = call(token, "getUpdates", timeout=0)
        if not updates.get("ok"):
            print("getUpdates-fout:", updates)
            sys.exit(1)
        chats = collect_chats(updates)
        if chats:
            break
        print(f"\nNog geen bericht gezien (poging {attempt}/5).")
        input(f"→ Open https://t.me/{uname}, druk op START (of typ /start), "
              "en druk dan hier op Enter ... ")

    if not chats:
        print("\n❌ Nog steeds geen chat gevonden. Meest voorkomende oorzaken:")
        print(f"   1) Je schreef naar een andere bot dan @{uname}.")
        print("   2) Je drukte Enter vóórdat /start verstuurd was.")
        print("   3) Berichten ouder dan 24 uur worden niet meer getoond.")
        print("\nRuwe getUpdates-respons:", updates)
        sys.exit(1)

    print("\nGevonden chats:")
    for cid, name in chats.items():
        print(f"  {cid}  {name}")

    chosen = str(next(iter(chats)))
    env["TELEGRAM_BOT_TOKEN"] = token
    env["TELEGRAM_CHAT_ID"] = chosen
    write_env(env)
    print(f"\n✅ Opgeslagen in {ENV}  (chat-id {chosen})")
    print("Test met:  .venv/bin/python deals.py test-telegram")


if __name__ == "__main__":
    main()
