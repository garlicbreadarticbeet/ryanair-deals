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

## Multi-user backend (in ontwikkeling — Fase B)

De single-user CLI hierboven blijft ongewijzigd werken. Daarnaast wordt een
multi-user kern opgebouwd onder `app/`, met PostgreSQL i.p.v. `state.json` en een
uitbreidbare provider-/kanaal-architectuur.

### Architectuur

```
app/
  settings.py     # centrale config via env (pydantic-settings)
  providers/      # maatschappij-adapters achter één FlightProvider-interface
                  #   base.py (DailyFare/Route + Protocol), registry.py,
                  #   ryanair.py (bewezen logica ingepakt), wizzair.py (stub)
  core/           # provider- én kanaal-agnostisch
                  #   combine.py (retour-combinatie), horizon.py
  channels/       # Notifier-interface (Telegram/e-mail/WhatsApp) — Fase C
  db/             # SQLAlchemy-modellen, sessie, seed (airports.json)
  web/            # FastAPI (health, magic-link, voorkeuren) — Fase C
migrations/       # Alembic
tests/            # o.a. no-regression: combine == bewezen deals.best_returns
```

Twee uitbreidingspunten, elk **één nieuw bestand**:
- **Nieuwe maatschappij** → adapter onder `app/providers/` die het `FlightProvider`-
  Protocol implementeert + een rij in de `providers`-tabel. `app/core/` verandert niet
  (een test bewaakt dat `core/` geen maatschappij-/kanaalnamen bevat).
- **Nieuw kanaal** → Notifier onder `app/channels/` (Fase C).

### Database opzetten (lokaal / Docker)

```bash
docker compose up -d db                      # Postgres op poort 5433 (geïsoleerd)
.venv/bin/alembic upgrade head               # schema aanmaken (9 tabellen)
.venv/bin/python -m app.db.seed_airports     # luchthavens + providers seeden
```

Config staat in `.env` (zie `.env.example`): `DATABASE_URL`, `TELEGRAM_*`,
`RESEND_API_KEY`, `ENABLED_PROVIDERS`, en de standaard-voorkeuren. Nooit in git.

### Tests

```bash
.venv/bin/python -m pytest        # incl. no-regression-bewijs voor de combine-logica
```

> De luchthavenlijst (`app/db/data/airports.json`) is een gebundelde momentopname van
> Ryanair's publieke airports-endpoint; verversen kan met
> `python scripts/refresh_airports.py`.
