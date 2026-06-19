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
architectuur, accounts + voorkeuren, een ontkoppelde **scan → match → notify**-lus, kanalen
Telegram + e-mail, en een **premium-abonnement** (Lemon Squeezy als Merchant of Record, Mollie
als latere optie) met instant-vs-digest-alerts. De primaire interface is een **server-rendered website**
(FastAPI + Jinja2); de Telegram-bot en de JSON-API zijn aanvullende kanalen op dezelfde kern.

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
                     #   telegram.py, email.py (Resend)
  alerts/            # presentatielaag: verrijking (stad/vlag/dealscore), gedeelde opmaak,
                     #   gebrande deal-kaart (card.py, Pillow) voor Telegram-foto + mail-hero
  db/                # SQLAlchemy-modellen, sessie, repo (queries), seed (airports.json)
  web/               # FastAPI: JSON-API (main.py) + website (views.py, templates/, static/),
                     #   deps.py (DB + cookie/Bearer-auth), auth.py (magic-link/sessietokens)
  billing.py             # provider-agnostische billing-service (checkout/cancel/tier + webhooks)
  billing_providers/     # BillingProvider-registry: lemonsqueezy_provider.py, mollie_provider.py
  lemonsqueezy.py, mollie.py  # dunne REST-clients per betaalprovider
  accounts.py        # onboarding-service (Telegram + e-mail) + voorkeuren
  dispatch.py        # stuurt gematchte deals naar de kanalen van een gebruiker
  telegram_handlers.py  # multi-user botcommando's
  worker.py          # scan -> match -> notify-lus (once / scheduler)
migrations/          # Alembic
tests/               # o.a. no-regression (combine == deals.best_returns) + DB-tests
```

Drie uitbreidingspunten, elk **één nieuw bestand**:
- **Nieuwe maatschappij** → adapter onder `app/providers/` die het `FlightProvider`-
  Protocol implementeert + een rij in de `providers`-tabel. `app/core/` verandert niet
  (een test faalt als `core/` een maatschappij-/kanaal-/betaalprovidernaam bevat).
- **Nieuw kanaal** → een `Notifier` onder `app/channels/` + registratie. `core/` verandert niet.
- **Nieuwe betaalprovider** → een `BillingProvider` onder `app/billing_providers/` + registratie;
  selecteerbaar via `BILLING_PROVIDER`. `core/` en `billing.py` (tier-flip) verlaten niet.

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
.venv/bin/python -m app.worker once          # één scan + instant-alerts (premium)
.venv/bin/python -m app.worker digest        # één digest-ronde (gratis-gebruikers)
.venv/bin/python -m app.worker run           # blijven draaien: instant elke 4u + dagelijkse digest
.venv/bin/python bot.py --forever            # Telegram-bot (onboarding + commando's)
.venv/bin/python bot.py --register           # /-commandomenu (her)instellen
.venv/bin/uvicorn app.web.main:app           # website + JSON-API
```

### Website

De website (server-rendered, `app/web/`) is de hoofdinterface en is gebouwd volgens
`Website-Plan-Vliegseintje.md` + `Merkidentiteit-Vliegseintje.md` (merk **Vliegseintje**,
tagline "Goedkoop vliegen, zonder zoeken."). Zie `DECISIONS.md` voor de stack-keuze
(Python/Jinja i.p.v. de in het plan genoemde Next.js) en aannames.

**Designsysteem** — `app/web/static/style.css` implementeert de tokens uit het plan §4
(kleuren, type-schaal, spacing, radii, schaduw, motion) als CSS custom properties.
Fonts (Poppins + Inter) zijn **self-hosted** onder `static/fonts/` (AVG, geen externe call).
Logo/favicon: `templates/_logo.html` + `static/favicon.svg` (vliegtuigje + amber "ping").

**Publieke marketingpagina's** (`app/web/marketing.py`):
`/` homepage · `/hoe-het-werkt` · `/premium` · `/bestemmingen` (voorbeelddata) · `/over-ons` ·
`/faq` (FAQPage-schema) · `/contact` (honeypot + rate-limit → `contact_messages`) ·
`/blog` + `/blog/<slug>` · `/privacy` `/voorwaarden` `/cookies` (placeholder-concepten) ·
`/robots.txt` · `/sitemap.xml` · nette `404`.

**Content** staat los van de code onder `app/web/content/` en wordt geladen via
`content_store.py`: blog + legal als Markdown (met `markdown` gerenderd), FAQ + voorbeeld-
bestemmingen als JSON. SEO-basis (per-pagina title/description/canonical/OG, JSON-LD
Organization/Article/FAQPage) zit in `templates/base.html`.

**Ingelogde app** (app-shell met zijbalk, `templates/app_base.html`):
`/login` + `/verify` (magic-link, cookie-sessie) · `/dashboard` (je deals) ·
`/preferences` (vertrekvelden, drempel, reisduren, filters) · `/channels` (Telegram koppelen,
e-mail) · `/account` (upgrade naar maand/jaar, opzeggen, account verwijderen).

Voor de Telegram-koppelknop: zet `TELEGRAM_BOT_USERNAME` in `.env`. Merk/social/analytics zijn
optioneel te overschrijven via env (zie `.env.example`). De JSON-API blijft beschikbaar
(o.a. `/health`, `/billing/webhook` voor Mollie en `/billing/lemonsqueezy/webhook` voor Lemon Squeezy).

Botcommando's: `/start` (account aanmaken/koppelen), `/origins EIN NRN`, `/drempel 50`,
`/reisduren 3 5 7`, `/mij`, `/deals` (uit de DB), `/stop` (account + data wissen).

### Deploy op Hetzner (volledige stack)

Volledige stap-voor-stap handleiding: **[DEPLOY.md](DEPLOY.md)**. Kort:

```bash
cp .env.example .env                          # vul SITE_DOMAIN, secrets, Travelpayouts, ...
docker compose --profile prod up -d --build   # incl. Caddy (auto-HTTPS op SITE_DOMAIN)
```

Start `db` + `migrate` (alembic + seed, eenmalig) + always-on `worker`, `bot`, `web` en — in het
`prod`-profiel — **`caddy`** als reverse proxy met automatische Let's Encrypt-HTTPS. Zonder profiel
(`docker compose up`) draait alles behalve Caddy, handig lokaal. Alles geïsoleerd onder projectnaam
`goedkoopvliegen`, Postgres op hostpoort **5433** zodat een ander project niet botst.

> GitHub Actions (`.github/workflows/`) blijft als alternatief bestaan, maar de cron staat
> standaard **uit** — draai het niet tegelijk met de always-on worker (dubbele alerts).

### Migratie `state.json` → Postgres

`state.json` was single-user dedup-historie en is **niet** als data gemigreerd: hij is uit
git gehaald (`git rm --cached`) en de cloud committeert hem niet meer terug. De per-gebruiker
dedup zit nu in de `sent_alerts`-tabel. De eerste multi-user run kan daardoor eenmalig de
huidige deals (opnieuw) melden; daarna is het stil tenzij een deal nieuw of goedkoper is.

### Premium / abonnement (Fase 2)

Premium-features (instelbaar via `PREMIUM_ONLY_FEATURES`, default `mode:instant`): **instant
alerts**, **meer vertrekvelden** (gratis = `FREE_MAX_ORIGINS`) en **uitgebreide prijsgeschiedenis**.
Gratis krijgt een **dagelijkse digest**, beperkte velden, en de kanalen Telegram + e-mail. De
policy zit op één plek: `app/core/gating.py` (`can_use`, `max_origins`, `effective_alert_mode`) —
gevoed door settings, zodat `core/` vrij blijft van kanaal-/maatschappij-/betaalprovidernamen.

**Maand- of jaarplan** (€ 2,99 / maand of € 24,99 / jaar; jaar is ~30% goedkoper en staat als
aanrader uitgelicht op `/premium` en `/account`). Prijzen komen volledig uit config
(`PREMIUM_PRICE_MONTHLY`/`PREMIUM_PRICE_ANNUAL`); de besparing/maandprijs wordt berekend
(`settings.premium_pricing`) en via de view-context aan de templates gegeven.

**Abonnement, provider-agnostisch.** `app/billing.py` is een dunne service die op
`BILLING_PROVIDER` de juiste `BillingProvider` kiest (`app/billing_providers/`) en de tier op
één plek op-/afschaalt. Twee providers:
- **Lemon Squeezy** (default; Merchant of Record → innen **zonder KvK**, EU-btw geregeld):
  client in `app/lemonsqueezy.py`, webhook `POST /billing/lemonsqueezy/webhook`
  (HMAC-SHA256 `X-Signature` over de rauwe body). Config: `LEMONSQUEEZY_API_KEY`,
  `LEMONSQUEEZY_STORE_ID`, `LEMONSQUEEZY_VARIANT_MONTHLY/ANNUAL`, `LEMONSQUEEZY_WEBHOOK_SECRET`.
- **Mollie** (latere optie na KvK): client in `app/mollie.py`, webhook `POST /billing/webhook`.
  Config: `MOLLIE_API_KEY`, `MOLLIE_INTERVAL_MONTHLY/ANNUAL`.

Endpoints in `app/web/main.py`: `POST /billing/checkout` (sessietoken; neemt `plan` =
`monthly`/`annual`) → checkout-URL van de actieve provider; `DELETE /billing/subscription` →
opzeggen. De webhooks vereisen dat `APP_BASE_URL` publiek (HTTPS) bereikbaar is.

### Alerts (Telegram + e-mail) + dealscore

De alert-content zit in `app/alerts/`: de scan houdt prijsgeschiedenis bij
(`deal_price_points`, migratie 0006) en daaruit berekent `app/core/scoring.py` een **dealscore**
("X% onder normaal", "laagste in N dagen"). Alerts ranken op **dealsterkte** (spannendste eerst).
De gedeelde render-laag geeft Telegram, e-mail én de **gebrande deal-kaart** (PNG, `card.py` met
Pillow + gebundelde merk-TTF's) hetzelfde: stadsnaam + vlag, dealscore-badge, boekknop. De e-mail
is een gebrande responsive HTML-mail; de Telegram-melding bevat een foto-kaart van de beste deal.
De mail-hero laadt via de **ondertekende** `/cards/deal.png`-endpoint (`ALERT_CARD_SECRET`); zonder
secret/Pillow valt alles schoon terug op tekst/HTML zonder beeld. De dealscore **warmt op** over
enkele dagen historie.

### Nog open (toekomst)

- **Gemengde carriers** (heen Ryanair, terug Wizz) → `# TODO(mixed-carrier)` in `app/core/combine.py`.
- **Wizz Air-adapter** → `app/providers/wizzair.py` invullen + provider op `enabled` zetten.

### Acceptatiecriteria

| # | Criterium | Status |
|---|---|---|
| 1 | Nieuwe maatschappij = 1 adapter, geen wijziging in match/combine/notify | ✅ registry + core-purity-test |
| 2 | Meerdere origins; scan op gededupte unie (schaalt niet met #users) | ✅ `repo.deduped_origin_targets` + test |
| 3 | `state.json` → Postgres; per-user dedup via `sent_alerts` | ✅ `core/dedup.py` (== detect_new_deals) |
| 4 | Twee users, andere voorkeuren → aantoonbaar andere alerts | ✅ `test_match_two_users` |
| 5 | Telegram + e-mail werken (uitbreidbare kanaal-registry) | ✅ `app/channels/` |
| 6 | Tests groen; migraties schoon op lege DB; README + `.env.example` bij | ✅ |
| 7 | Netwerk via requests/certifi; geen geheimen in git | ✅ `app/net.py`, env-only |

> De luchthavenlijst (`app/db/data/airports.json`) is een gebundelde momentopname van
> Ryanair's publieke airports-endpoint; verversen kan met `python scripts/refresh_airports.py`.
