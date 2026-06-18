# Claude Code build-opdracht — "Goedkoop Vliegen" van prototype naar multi-user dienst

> Plak dit als openingsbericht in Claude Code, **in de root van deze repo**
> (`ryanair-deals`). Het beschrijft wat er al is, wat je moet bouwen, de
> architectuurkeuzes en hoe je te werk gaat. Lees eerst de hele opdracht, stel
> dan je verduidelijkende vragen, en begin pas met code na akkoord op het
> voorstel uit "Fase A".

---

## 1. Rol & doel

Je bent een senior Python-engineer. Je bouwt een bestaand **single-user**
Ryanair-deal-prototype om naar de **multi-user kern** van een betaalde
freemium-dienst. De nadruk ligt op een schone, uitbreidbare architectuur — niet
op het meteen af hebben van alle features.

**Twee eisen die de architectuur sturen (belangrijk):**

1. **Gebruikers kiezen zelf hun vliegvelden** — elke gebruiker selecteert één of
   *meerdere* vertrekvelden. Niets mag hardgecodeerd zijn op EIN/NRN. Een
   centrale lijst van ondersteunde luchthavens; per gebruiker een eigen selectie.
2. **De airline-laag moet uitbreidbaar zijn** — nu alleen Ryanair, maar later
   **Wizz Air en andere prijsvechters**. Ontwerp daarom een *provider-interface*
   waar elke maatschappij een adapter voor is. De rest van het systeem (matchen,
   combineren, alerten) werkt op een genormaliseerd datamodel en kent geen enkele
   maatschappij-specifiek detail.

---

## 2. Wat er al is (hergebruiken, niet weggooien)

Dit draait en werkt. Behoud de bewezen scan-/combinatielogica.

| Bestand | Inhoud |
|---|---|
| `config.py` | Instellingen: `ORIGINS`, `MONTHS_AHEAD`, `TRIP_LENGTHS`, `ALERT_THRESHOLD`, `CONCURRENCY`, bestemmingsfilters |
| `deals.py` | Kern: `fetch_perday(session, orig, dest, months)`, `best_returns(...)`, `scan(verbose)`, `detect_new_deals(units, state, threshold, now_iso)`, `format_telegram(...)`, `load_state`/`save_state`, CLI `scan`/`watch`/`test-telegram` |
| `notify.py` | `send_telegram(text)`, `telegram_configured()` — via `requests` + `certifi` |
| `bot.py` | Telegram-polling: `handle_update`, `poll_forever`, `register_commands`, `deals_summary` (`/deals`, `/help`) |
| `setup_telegram.py` | Eenmalige helper token + chat-id → `.env` |
| `.github/workflows/` | `scan.yml` (elke 4u: `python deals.py watch`), `bot.yml` (elke ~5 min: commando's) |
| `data/state.json` | Dedup van eerder gemelde prijzen (single-user) |

Databron nu: `ryanair-py` + Ryanair's publieke `farfnd/v4` (`cheapestPerDay`/
`oneWayFares`), geen API-key.

**Harde regels uit de project-overdracht (`handoff.md`) — niet schenden:**

- **Netwerkcalls via `requests` (+ `certifi`), nooit terug naar `urllib`** — de
  Homebrew-OpenSSL cert-store gaf `CERTIFICATE_VERIFY_FAILED`. Laat staan.
- De cloud commit `data/state.json` terug; daar komt straks de database voor in
  de plaats (geen state meer in git).
- GitHub pauzeert geplande workflows na 60 dagen inactiviteit (1 klik "Enable").

---

## 3. Scope van déze opdracht (Fase 1 + fundament)

**Wel bouwen:**

- Genormaliseerd datamodel + **PostgreSQL** (vervangt `state.json`).
- **Provider-interface** voor maatschappijen; **Ryanair-adapter** die de
  bestaande logica inpakt. Wizz-adapter alleen als *stub* met duidelijke TODO.
- **Per-gebruiker voorkeuren**: meerdere vertrekvelden, bestemmingsfilter,
  reisduren, prijsdrempel, valuta.
- Ontkoppeling **scan → match → notify** (zie §4).
- **Kanalen**: Telegram (bestaand) + **e-mail** (transactioneel). WhatsApp als
  interface/stub voor later.
- **Accounts & onboarding**: Telegram `/start`-deeplink koppelt chat-id aan
  account; e-mail magic-link; voorkeurenbeheer via botcommando's en een minimale
  web-API.
- **Scheduler/worker** die periodiek scant en alerts verstuurt (lokaal draaibaar;
  GitHub Actions blijft als alternatief mogelijk).
- Tests, migraties, README-update.

**Bewust NIET bouwen (wel "naden" voorzien):**

- Betalingen/Mollie en de gratis-vs-premium *gating-logica* (alleen een
  `tier`-veld + een centrale `can_use(feature)` plek voorzien).
- WhatsApp daadwerkelijk versturen (alleen de interface).
- Volledige web-UI / landingspagina, SEO, referrals.

> Vraag mij of het scopen klopt voordat je begint. Een vervolgprompt voor Fase 2
> (betalingen + premium-gating + WhatsApp) volgt later.

---

## 4. Architectuur

### 4.1 Provider-interface (maatschappij-agnostisch)

Definieer een abstracte `FlightProvider` met genormaliseerde types, zodat een
nieuwe maatschappij = één nieuwe adapter, zonder de rest aan te raken.

```python
# providers/base.py  (richting, geen letterlijke eis)
@dataclass(frozen=True)
class DailyFare:
    provider: str          # "ryanair", "wizzair", ...
    origin: str            # IATA
    destination: str       # IATA
    date: datetime.date
    price: float
    currency: str

class FlightProvider(Protocol):
    name: str
    def supported_origins(self, candidate_origins: list[str]) -> list[str]: ...
    def routes(self, origin: str) -> list[str]: ...            # bestemmingen (IATA)
    def daily_fares(self, origin: str, destination: str,
                    months: list[str]) -> list[DailyFare]: ...  # heen- én terugrichting
```

- `RyanairProvider` verpakt de bestaande `fetch_perday` / route-ontdekking.
- De **retour-combinatielogica** (`best_returns`: goedkoopste heen op dag D +
  terug op dag D+N, per reisduur N) verhuist naar een **provider-onafhankelijke**
  module die op `DailyFare`-lijsten werkt. Combineer voorlopig binnen dezelfde
  `provider`+route (gemengde carriers = expliciete TODO voor later).
- Een **registry** mapt providernaam → adapter, zodat providers via config aan/uit
  kunnen.

### 4.2 Vliegvelden (gebruiker-selecteerbaar)

- Eén bron van waarheid voor ondersteunde luchthavens (IATA, naam, land), als
  seed-data in de database (geen hardcode in businesslogica).
- Een gebruiker kiest een **set** origins. De scanner werkt op de **unie** van
  alle door gebruikers gekozen `(provider, origin)`-paren — globaal en gededupt,
  zodat de scan niet meeschaalt met het aantal gebruikers.

### 4.3 Datamodel (PostgreSQL via SQLAlchemy 2.x + Alembic)

Stel het exacte schema voor en vraag akkoord. Richting:

- `users` — id, aangemaakt, status, **tier** (`free`/`premium`), e-mail (optioneel
  tot verificatie).
- `channels` — user_id, type (`telegram`/`email`/`whatsapp`), adres/chat_id,
  `verified` (bool), opt-in-tijdstip.
- `preferences` — user_id, `origins` (lijst IATA), bestemmingsfilter
  (land/whitelist/blacklist), `trip_lengths`, `threshold`, valuta, alert-modus
  (`instant`/`digest`).
- `airports` — IATA, naam, land (seed).
- `deals` — provider, origin, destination, out_date, in_date, trip_len,
  total_price, currency, found_at. (Globaal; vervangt de "units" in `state.json`.)
- `sent_alerts` — user_id, deal-fingerprint, channel, sent_at. (Per-gebruiker
  dedup; vervangt globale `state.json`.)

### 4.4 Scan → match → notify (ontkoppeld)

1. **Scan** (per provider, per unieke origin): vul/ververs `deals`. Politeness:
   houd `CONCURRENCY`-achtige beperking en caching aan; respecteer rate limits.
2. **Match** (per gebruiker): vergelijk relevante `deals` met `preferences`,
   bepaal *nieuwe of goedkopere* matches t.o.v. `sent_alerts` (dezelfde
   dedup-gedachte als `detect_new_deals`, maar per gebruiker en in de DB).
3. **Notify**: dispatch per kanaal via een `Notifier`-interface
   (`TelegramNotifier`, `EmailNotifier`, `WhatsAppNotifier`-stub). Free-tier:
   Telegram + e-mail (digest). De gating-beslissing achter één
   `can_use(user, feature)`-functie (voor Fase 2).

### 4.5 Web/worker

- **Worker**-entrypoint die scan→match→notify periodiek draait (APScheduler of een
  simpele loop). Lokaal draaibaar; GitHub Actions blijft optioneel mogelijk.
- Minimale **FastAPI**-app voor: health-check, magic-link-verificatie,
  voorkeuren-endpoints en (later) Mollie-webhooks. Houd 'm klein.

---

## 5. Tech-stack & conventies

- Python 3.12+; behoud `ryanair-py`, `requests`, `certifi`.
- SQLAlchemy 2.x + Alembic (migraties), Pydantic (schema's/validatie),
  FastAPI + Uvicorn (web), APScheduler (scheduler), `pytest` (tests).
- Config & secrets via **env vars** (pydantic-settings); `.env` lokaal, nooit in
  git. Werk `.env.example` bij.
- Nette structuur, type hints, docstrings in het **Nederlands** (consistent met de
  bestaande codebase). Kleine, gefocuste modules.
- **GDPR-bewust**: sla minimale PII op, expliciete opt-in per kanaal (zeker
  WhatsApp), en voorzie een `delete_user`-pad (recht op verwijdering).

Voorgestelde mapindeling (pas gerust aan en leg uit):

```
app/
  providers/      base.py, registry.py, ryanair.py, wizzair.py (stub)
  core/           combine.py (retour-combinatie), match.py, dedup.py
  channels/       base.py, telegram.py, email.py, whatsapp.py (stub)
  db/             models.py, session.py, seed_airports.py
  web/            main.py (FastAPI), auth.py (magic-link)
  worker.py       scan -> match -> notify loop
  settings.py
migrations/        (alembic)
tests/
```

---

## 6. Werkwijze (volg deze fasering)

**Fase A — Ontwerp eerst, code daarna.** Lever een kort voorstel: definitief
DB-schema, de `FlightProvider`-interface, de mapindeling en een migratieplan van
`state.json` → Postgres. **Wacht op mijn akkoord.**

**Fase B — Fundament.** DB-modellen + Alembic-migraties + airport-seed.
Provider-interface + `RyanairProvider` (bestaande logica ingepakt). Verplaats de
retour-combinatie naar `core/combine.py`. Tests die bewijzen dat de output gelijk
is aan de huidige `scan()` voor dezelfde input (geen regressie).

**Fase C — Multi-user.** Accounts, kanalen, voorkeuren (incl. *meerdere*
origins). Scan→match→notify ontkoppeld. Telegram-onboarding via `/start`-deeplink;
voorkeuren via botcommando's; e-mailkanaal + magic-link.

**Fase D — Afronding.** Worker-entrypoint, README + `.env.example` bijwerken,
testsuite groen, korte migratiehandleiding. Maak duidelijk welke "naden" klaarstaan
voor Fase 2 (Mollie/gating/WhatsApp).

**Algemeen:**

- Werk in kleine commits met duidelijke berichten; draai tests per stap.
- Breek de bestaande CLI (`scan`/`watch`) niet zonder het te benoemen.
- **Stel een verduidelijkende vraag** wanneer iets onderbepaald is (bv. waar ik wil
  hosten, of ik Postgres lokaal/Docker/managed wil) in plaats van aan te nemen.
- Verzin geen prijzen of feiten; dit is een technische bouwopdracht.

---

## 7. Acceptatiecriteria

- [ ] Een nieuwe maatschappij toevoegen = één adapter onder `providers/`, zonder
      wijzigingen in match-/combine-/notify-code.
- [ ] Een gebruiker kan **meerdere** vertrekvelden kiezen; de scan draait op de
      gededupte unie van alle gekozen origins.
- [ ] `state.json` is vervangen door Postgres; dedup gebeurt **per gebruiker** via
      `sent_alerts`.
- [ ] Twee gebruikers met verschillende voorkeuren krijgen aantoonbaar
      verschillende alerts (test).
- [ ] Telegram + e-mail werken; WhatsApp bestaat als interface/stub.
- [ ] Tests groen; migraties draaien schoon op een lege DB; README + `.env.example`
      bijgewerkt.
- [ ] Netwerkcalls nog steeds via `requests`/`certifi`; geen geheimen in git.

---

## 8. Eerste actie

Lees `handoff.md`, `config.py`, `deals.py`, `notify.py` en `bot.py`. Lever dan het
voorstel uit **Fase A** (schema + provider-interface + mapindeling + migratieplan)
en je verduidelijkende vragen. Begin niet met implementeren vóór mijn akkoord.
