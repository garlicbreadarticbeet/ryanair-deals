# Handoff — Ryanair retour-deal-scanner

Korte overdracht van wat dit project is, wat het doet en hoe het draait.

## Wat het is
Een tool die de **goedkoopste Ryanair-retourvluchten** vindt vanaf NL- en
grensvelden, en je via een **Telegram-bot** waarschuwt bij nieuwe koopjes.
Gebouwd op [`ryanair-py`](https://github.com/cohaolain/ryanair-py) + Ryanair's
publieke `cheapestPerDay`-API. Geen API-key nodig.

- **Repo:** https://github.com/garlicbreadarticbeet/ryanair-deals (openbaar)
- **Bot:** @goedkoopvliegen_bot ("Goedkoop Vliegen")
- **Vertrekvelden:** Eindhoven (EIN), Weeze (NRN), Amsterdam (AMS), Maastricht (MST), Groningen (GRQ).
  In de praktijk leveren **EIN** en **NRN** vrijwel al het aanbod; AMS ~2 routes, MST/GRQ 0 (Ryanair vliegt daar niet).

## Wat het doet
- Per bestemming de goedkoopste **retour (heen+terug)** voor een trip van **3, 5 en 7 dagen**, tot **3 maanden** vooruit.
- **Alerts** in Telegram bij elke nieuwe of goedkopere retour onder **€50 totaal**, gegroepeerd per reisduur.
- **Commando's** in de bot: `/deals` (volledig actueel overzicht + bijlage), `/help`.

## Hoe het werkt
1. **Routes ontdekken:** `ryanair-py` geeft per vertrekveld de bestaande bestemmingen.
2. **Prijzen per dag:** voor elke route worden via `farfnd/v4/.../cheapestPerDay` de
   dagprijzen opgehaald — **heen én terug** — over alle maanden in de horizon (parallel, ~10 sec totaal).
3. **Combineren:** voor elke reisduur N (3/5/7) wordt de goedkoopste combinatie gezocht:
   vertrek op dag D, terug op dag D+N. Laagste totaal per (route, N) wint.
4. **Alerten:** `state.json` onthoudt eerder gemelde prijzen, zodat alleen *nieuwe* of
   *goedkopere* deals een melding geven (geen spam).

## Draaien (cloud — altijd aan, geen laptop nodig)
GitHub Actions, twee workflows in `.github/workflows/`:
- **`scan.yml`** — elke 4 uur: `python deals.py watch` → alerts versturen + `state.json` terugcommitten.
- **`bot.yml`** — elke ~5 min: `python bot.py` → kijkt of er commando's (`/deals`) zijn en beantwoordt ze.

Secrets staan als **GitHub Actions Secrets**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Lokaal draaien (optioneel)
```bash
.venv/bin/python deals.py scan            # tabel + data/report.md|csv
.venv/bin/python deals.py watch           # scan + alert
.venv/bin/python deals.py test-telegram   # testbericht
.venv/bin/python bot.py --forever         # bot lokaal laten luisteren
.venv/bin/python bot.py --register        # /-menu + beschrijvingen (her)instellen
```
Lokaal leest Telegram-creds uit `.env` (niet in git); in de cloud uit Secrets.
De `launchd`-bestanden (`run-watch.sh`, `com.ryanairdeals.watch.plist`) zijn een
backup om het lokaal periodiek te draaien, maar **overbodig** nu de cloud alles doet.

## Aanpassen
Alles staat bovenin [`config.py`](config.py): `ORIGINS`, `MONTHS_AHEAD`,
`TRIP_LENGTHS` (de kolommen), `ALERT_THRESHOLD` (€, totaal), `CONCURRENCY`, en
filters (`DESTINATION_COUNTRY`, `ONLY_DESTINATIONS`, `EXCLUDE_DESTINATIONS`).
Wijzig → push. Pas je `TRIP_LENGTHS`/`ALERT_THRESHOLD` aan, draai dan ook
`bot.py --register` (bot-teksten verwijzen ernaar).

## Bestanden
| Bestand | Doel |
|---|---|
| `config.py` | Alle instellingen |
| `deals.py` | Scan, combinatie-logica, rapporten, alert-detectie (`scan`/`watch`) |
| `bot.py` | Telegram-commando's, beschrijvingen (`/deals`, `/help`) |
| `notify.py` | Telegram versturen (via `requests`) |
| `setup_telegram.py` | Eenmalige helper voor token + chat-id → `.env` |
| `.github/workflows/` | `scan.yml` (alerts), `bot.yml` (commando's) |
| `data/` | `report.md`, `report.csv`, `state.json` (niet in git, behalve state via de cloud) |

## Belangrijk om te weten (valkuilen)
- **`git pull` vóór lokaal pushen:** de cloud commit `data/state.json` terug, dus je lokale repo loopt achter.
- **GitHub pauzeert geplande workflows na 60 dagen** zonder repo-activiteit → 1 klik "Enable" in de Actions-tab.
- **Openbare repo:** code is publiek, maar de Telegram-creds zitten alleen in versleutelde Secrets (niet in de code).
- **SSL-keuze:** netwerk-calls gaan bewust via `requests` (certifi), niet `urllib` — de Homebrew-OpenSSL cert-store op de Mac is incompleet en gaf `CERTIFICATE_VERIFY_FAILED`. Niet terugzetten naar `urllib`.
