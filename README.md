# Ryanair retour-deal-scanner

Vindt per bestemming de **goedkoopste retour (heen + terug)** voor een trip van
**3, 5 en 7 dagen** (drie kolommen), vanaf jouw vertrekvelden, voor de komende
maanden — en stuurt een **Telegram-alert** zodra er een nieuwe retour onder je
drempel (standaard €50 totaal) opduikt.

Gebouwd op [`ryanair-py`](https://github.com/cohaolain/ryanair-py) + Ryanair's
`cheapestPerDay`-API. Geen API-key nodig.

Vertrekvelden: **Amsterdam (AMS), Eindhoven (EIN), Weeze (NRN), Maastricht (MST),
Groningen (GRQ)**.
> Let op: Ryanair vliegt nauwelijks vanaf Schiphol en niet vanaf Maastricht/Groningen.
> **Eindhoven** en **Weeze** leveren in de praktijk vrijwel al het aanbod.

## Hoe het werkt

Voor elke route worden de prijzen **per dag** opgehaald (heen én terug). Daarna
wordt voor elke reisduur de goedkoopste combinatie gezocht: vertrek op dag D,
terug op dag D+3 / D+5 / D+7. De getoonde prijs is steeds **heen + terug samen**.

## Gebruik

```bash
# Tabel: goedkoopste 3/5/7-daagse retour per bestemming (schrijft data/report.md + .csv)
.venv/bin/python deals.py scan

# Scan + Telegram-alert bij nieuwe deals onder de drempel
.venv/bin/python deals.py watch

# Testbericht naar Telegram
.venv/bin/python deals.py test-telegram
```

Resultaten:
- `data/report.md`  — tabel met 3 kolommen (3/5/7 dagen), prijs + heen→terug-datum
- `data/report.csv` — élke route met per reisduur prijs/heen/terug (voor Excel)
- `data/state.json` — onthoudt prijzen zodat alerts alleen bij iets *nieuws* afgaan

## Telegram (al ingesteld)

Staat in `.env` (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`). Opnieuw instellen:
`.venv/bin/python setup_telegram.py`.

## Automatisch laten draaien (macOS, elke 4 uur)

```bash
cp com.ryanairdeals.watch.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.ryanairdeals.watch.plist
```

Stoppen: `launchctl unload -w ~/Library/LaunchAgents/com.ryanairdeals.watch.plist`.
Interval staat in het plist onder `StartInterval` (seconden). Logs: `data/watch.log`.

## Aanpassen

Alles staat bovenin [`config.py`](config.py):
- `ORIGINS` — vertrekvelden
- `MONTHS_AHEAD` — hoe ver vooruit (nu 3)
- `TRIP_LENGTHS` — de reisduren/kolommen (nu `[3, 5, 7]`)
- `ALERT_THRESHOLD` — alert-drempel voor de **totale** retourprijs (nu 50)
- `CONCURRENCY` — hoeveel routes tegelijk ophalen (nu 8; verlaag bij API-fouten)
- `DESTINATION_COUNTRY` / `ONLY_DESTINATIONS` / `EXCLUDE_DESTINATIONS` — filters

Drempel eenmalig overschrijven:
```bash
.venv/bin/python deals.py watch --threshold 40
```

---

## Multi-user dienst (`app/`)

De single-user CLI hierboven blijft ongewijzigd werken. Daarnaast staat onder `app/`
de multi-user kern: PostgreSQL i.p.v. `state.json`, een uitbreidbare provider-/kanaal-
architectuur, accounts + voorkeuren, een ontkoppelde **scan → match → notify**-lus, en
kanalen Telegram + e-mail (WhatsApp als stub).

### Architectuur

```
app/
  settings.py        # centrale config via env (pydantic-settings)
  net.py             # gedeelde requests+certifi-sessie (nooit urllib)
  providers/         # maatschappij-adapters achter één FlightProvider-interface
                     #   base.py (DailyFare/Route + Protocol), registry.py,
                     #   ryanair.py (bewezen logica ingepakt), wizzair.py (stub)
  core/              # provider- én kanaal-agnostisch (test bewaakt dat hier geen
                     #   maatschappij-/kanaalnaam in voorkomt)
                     #   combine.py (retour-combinatie), horizon.py,
                     #   scan.py (orkestratie), match.py (per-user), dedup.py, gating.py
  channels/          # Notifier-interface + registry
                     #   telegram.py, email.py (Resend), whatsapp.py (stub)
  db/                # SQLAlchemy-modellen, sessie, repo (queries), seed (airports.json)
  web/               # FastAPI (main.py) + magic-link/sessietokens (auth.py)
  accounts.py        # onboarding-service (Telegram + e-mail) + voorkeuren
  dispatch.py        # stuurt gematchte deals naar de kanalen van een gebruiker
  telegram_handlers.py  # multi-user botcommando's
  worker.py          # scan -> match -> notify-lus (once / scheduler)
migrations/          # Alembic
tests/               # o.a. no-regression (combine == deals.best_returns) + DB-tests
```

Twee uitbreidingspunten, elk **één nieuw bestand**:
- **Nieuwe maatschappij** → adapter onder `app/providers/` die het `FlightProvider`-
  Protocol implementeert + een rij in de `providers`-tabel. `app/core/` verandert niet
  (een test faalt als `core/` een maatschappij-/kanaalnaam bevat).
- **Nieuw kanaal** → een `Notifier` onder `app/channels/` + registratie. `core/` verandert niet.

### Lokaal opzetten

```bash
docker compose up -d db                      # Postgres op poort 5433 (geïsoleerd)
.venv/bin/alembic upgrade head               # schema aanmaken (9 tabellen)
.venv/bin/python -m app.db.seed_airports     # luchthavens + providers seeden
.venv/bin/python -m pytest                   # testsuite (incl. no-regression-bewijs)
```

Config staat in `.env` (kopieer `.env.example`): `DATABASE_URL`, `TELEGRAM_*`,
`RESEND_API_KEY`, `APP_BASE_URL`, `ENABLED_PROVIDERS`, en de standaard-voorkeuren.
Nooit in git.

### Draaien

```bash
.venv/bin/python -m app.worker once          # één scan -> match -> notify
.venv/bin/python -m app.worker run           # blijven draaien (elke 4 uur)
.venv/bin/python bot.py --forever            # Telegram-bot (onboarding + commando's)
.venv/bin/python bot.py --register           # /-commandomenu (her)instellen
.venv/bin/uvicorn app.web.main:app           # web-API (health, magic-link, /prefs)
```

Botcommando's: `/start` (account aanmaken/koppelen), `/origins EIN NRN`, `/drempel 50`,
`/reisduren 3 5 7`, `/mij`, `/deals` (uit de DB), `/stop` (account + data wissen).

### Deploy op Hetzner (volledige stack)

```bash
cp .env.example .env        # en vul je waarden in (token, Resend-key, ...)
docker compose up -d --build
```

Start `db` + `migrate` (alembic + seed, eenmalig) + always-on `worker`, `bot` en `web`.
Alles geïsoleerd onder projectnaam `goedkoopvliegen`, Postgres op hostpoort **5433** zodat
een ander project op dezelfde server niet botst.

> GitHub Actions (`.github/workflows/`) blijft als alternatief bestaan, maar de cron staat
> standaard **uit** — draai het niet tegelijk met de always-on worker (dubbele alerts).

### Migratie `state.json` → Postgres

`state.json` was single-user dedup-historie en is **niet** als data gemigreerd: hij is uit
git gehaald (`git rm --cached`) en de cloud committeert hem niet meer terug. De per-gebruiker
dedup zit nu in de `sent_alerts`-tabel. De eerste multi-user run kan daardoor eenmalig de
huidige deals (opnieuw) melden; daarna is het stil tenzij een deal nieuw of goedkoper is.

### Naden klaar voor Fase 2

- **Betalingen/premium-gating** → `app/core/gating.py` (`can_use(user, feature)`): vul
  `PREMIUM_ONLY_FEATURES` en voeg een Mollie-webhook toe in `app/web/main.py`. `tier`-veld staat klaar.
- **WhatsApp** → `app/channels/whatsapp.py` (interface bestaat; alleen `send()` invullen).
- **Gemengde carriers** (heen Ryanair, terug Wizz) → `# TODO(mixed-carrier)` in `app/core/combine.py`.
- **E-mail digest** → `alert_mode='digest'` staat in de voorkeuren; dispatch kan een digest-pad krijgen.

### Acceptatiecriteria

| # | Criterium | Status |
|---|---|---|
| 1 | Nieuwe maatschappij = 1 adapter, geen wijziging in match/combine/notify | ✅ registry + core-purity-test |
| 2 | Meerdere origins; scan op gededupte unie (schaalt niet met #users) | ✅ `repo.deduped_origin_targets` + test |
| 3 | `state.json` → Postgres; per-user dedup via `sent_alerts` | ✅ `core/dedup.py` (== detect_new_deals) |
| 4 | Twee users, andere voorkeuren → aantoonbaar andere alerts | ✅ `test_match_two_users` |
| 5 | Telegram + e-mail werken; WhatsApp als stub | ✅ `app/channels/` |
| 6 | Tests groen; migraties schoon op lege DB; README + `.env.example` bij | ✅ |
| 7 | Netwerk via requests/certifi; geen geheimen in git | ✅ `app/net.py`, env-only |

> De luchthavenlijst (`app/db/data/airports.json`) is een gebundelde momentopname van
> Ryanair's publieke airports-endpoint; verversen kan met `python scripts/refresh_airports.py`.
