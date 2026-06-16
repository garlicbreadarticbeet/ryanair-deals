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
