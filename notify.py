"""Telegram-notificaties. Gebruikt 'requests' (met certifi) — werkt waar de
systeem-OpenSSL-certificatenstore tekortschiet."""
import os
from pathlib import Path

import requests

_ENV = Path(__file__).resolve().parent / ".env"


def _load_env():
    """Laad TELEGRAM_* uit .env (zonder een externe lib)."""
    if not _ENV.exists():
        return
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def _token():
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id():
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def telegram_configured():
    return bool(_token() and _chat_id())


def _chunks(text, size=3900):
    """Splits netjes op regels onder Telegram's 4096-tekenlimiet."""
    if len(text) <= size:
        yield text
        return
    cur = ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size:
            yield cur
            cur = ""
        cur += line + "\n"
    if cur:
        yield cur


def send_telegram(text, chat_id=None, parse_mode="HTML"):
    # chat_id optioneel: valt terug op de env-eigenaar (single-user CLI-compat).
    # Multi-user: de dispatcher geeft per kanaal de chat_id mee.
    token = _token()
    chat_id = str(chat_id) if chat_id is not None else _chat_id()
    if not (token and chat_id):
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for chunk in _chunks(text):
        try:
            r = requests.post(url, data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": "true",
            }, timeout=20)
            resp = r.json()
            ok = ok and resp.get("ok", False)
            if not resp.get("ok"):
                print("Telegram-respons:", resp)
        except Exception as e:
            print(f"Telegram-fout: {e}")
            ok = False
    return ok
