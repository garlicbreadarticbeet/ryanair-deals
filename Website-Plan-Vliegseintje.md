# Vliegseintje — Bouwplan voor de website + app

**Versie:** 1.0 · **Datum:** 18 juni 2026 · **Doel:** complete build-spec die je 1-op-1 aan Claude Code kunt geven om de marketingsite, de app-UI én de backend te programmeren.

> **Hoe dit document te gebruiken (lees dit eerst, Claude Code):**
> Dit is de bron van waarheid voor het bouwen van Vliegseintje. Werk in de fasen uit sectie 18 (Build-volgorde). Bouw eerst het designsysteem en de marketingsite, daarna auth + app-UI, daarna de backend (datamodel, API, scan-engine, notificaties, betalingen). Houd je strikt aan het designsysteem (sectie 4) en de merkstem (sectie 5). Waar een externe dienst nodig is (flight-data, betalingen, e-mail, WhatsApp), abstraheer die achter een interface zodat de provider later te wisselen is. Vraag niet om elke kleine beslissing; volg de defaults hier en noteer aannames in `DECISIONS.md`.

---

## 1. Productsamenvatting

Vliegseintje is een **freemium webdienst** die automatisch de goedkoopste **retourvluchten** vindt vanaf de vertrekvelden die de gebruiker zelf kiest. De gebruiker stelt vertrekvelden, een prijsdrempel en gewenste reisduren in. De dienst controleert dagelijks de prijzen (start: Ryanair; later ook andere prijsvechters zoals Wizz Air) en stuurt een **seintje** zodra er een retour onder de drempel verschijnt — via **Telegram, e-mail** en (Premium) **WhatsApp**.

Onderdelen:
- **Marketingsite** (publiek): legt de propositie uit en zet bezoekers om naar een account.
- **App** (ingelogd): dashboard, alerts aanmaken/beheren, voorkeuren, account, abonnement.
- **Telegram-bot**: koppelt aan een account en levert alerts.
- **Backend**: auth, database, dagelijkse prijs-scan, notificatie-engine, betalingen.
- **Premium-abonnement**: instant alerts (i.p.v. dagelijkse digest), meerdere vertrekvelden, WhatsApp-kanaal.

**Doelgroep:** prijsbewuste vakantievliegers in Nederland en Vlaanderen — studenten, jonge stellen, citytrip-liefhebbers — flexibel in datum en bestemming. **Toon:** vriendelijk, nuchter-Nederlands, een tikje speels, betrouwbaar (geen schreeuwerige clickbait).

---

## 2. Doelen & niet-doelen

**Doelen (MVP → v1):**
1. Bezoeker begrijpt binnen 5 seconden wat Vliegseintje doet en maakt een gratis account aan.
2. Gebruiker stelt in < 2 minuten zijn eerste alert in (vertrekveld(en), drempel, reisduur, kanaal).
3. Het systeem scant dagelijks en stuurt betrouwbare, duidelijke alerts.
4. Gebruiker kan upgraden naar Premium (instant alerts, meer vertrekvelden, WhatsApp) en betalen via iDEAL/Bancontact.
5. Volledig AVG/GDPR-conform; privacyvriendelijke analytics.

**Niet-doelen (voor nu):**
- Geen eigen boekingsmotor: we **linken door** naar de airline/aggregator (affiliate waar mogelijk), we verkopen geen tickets zelf.
- Geen native mobiele apps in v1 (responsive web + Telegram dekt mobiel).
- Geen hotels/auto/pakketreizen — alleen vluchten.
- Geen prijsvoorspelling/AI-forecast in v1 (kan later).

---

## 3. Kritieke beslissing vooraf — databron voor vluchtprijzen (lees goed)

**Niet rechtstreeks Ryanair scrapen.** Ryanair verbiedt screen-scraping expliciet in zijn Terms of Use en handhaaft dit actief; Europese en Ierse rechtspraak (CJEU *Ryanair v PR Aviation*; Ierse High Court tegen "Flightbox") bevestigt dat zij scraping via hun voorwaarden mogen verbieden en blokkeren. Direct scrapen geeft juridisch risico én technisch risico (IP-blokkades, captchas, kapotte selectors).

**Aanbevolen aanpak — gebruik een vluchtdata-/aggregator-API** die low-cost carriers (incl. Ryanair en Wizz Air) legaal ontsluit, bij voorkeur met affiliate-vergoeding zodat doorverwijzingen ook inkomsten opleveren:
- **Primair:** Kiwi.com **Tequila** API (800+ airlines incl. low-cost, gratis testtier, affiliate/partnerprogramma) **of** een affiliate-netwerk zoals **Travelpayouts/Aviasales**.
- **Alternatieven om te evalueren:** Duffel, Amadeus Self-Service, Skyscanner Partners.
- **Implementatie-eis:** bouw de databron achter een interface `FlightDataProvider` (sectie 12.4) zodat we van provider kunnen wisselen of er meerdere kunnen combineren zonder de rest te raken.

> **Actie voor Tim (niet door Claude Code te verzinnen):** controleer de actuele voorwaarden, dekking en kosten van de gekozen API vóór livegang. Behandel "Ryanair-only scraping" als laatste redmiddel met juridisch advies. Claude Code: ga uit van de `FlightDataProvider`-interface en lever een werkende mock + één echte adapter (Tequila) op.

---

## 4. Designsysteem

Het designsysteem komt rechtstreeks uit de merkidentiteit. Implementeer als **CSS custom properties + Tailwind theme tokens** zodat alles centraal te wijzigen is.

### 4.1 Kleuren (tokens)

| Token | Naam | Hex | Gebruik |
|---|---|---|---|
| `--color-primary` | Hemelsblauw | `#2563EB` | Primaire knoppen, links, merkaccenten |
| `--color-primary-hover` | Hemelsblauw donker | `#1D4FD7` | Hover/active op primair |
| `--color-primary-soft` | Hemelsblauw zacht | `#E8F0FE` | Achtergrondvlakken, badges, highlights |
| `--color-accent` | Seintje-amber | `#FFB703` | De "ping": notificatie-accent, CTA-highlights, iconen |
| `--color-accent-hover` | Amber donker | `#E9A100` | Hover op accent |
| `--color-ink` | Nachtblauw | `#102A43` | Koppen en donkere tekst |
| `--color-body` | Lei-blauw | `#334E68` | Bodytekst |
| `--color-muted` | Mistblauw | `#627D98` | Secundaire/ondersteunende tekst |
| `--color-bg` | Wit | `#FFFFFF` | Hoofdachtergrond |
| `--color-surface` | Mistgrijs | `#F5F8FC` | Secties, kaarten, app-achtergrond |
| `--color-border` | Lichtgrijs | `#E3E9F2` | Randen, scheidingslijnen, inputs |
| `--color-success` | Dealgroen | `#20A779` | "Deal gevonden", prijs onder drempel, succes |
| `--color-warning` | Oranje | `#F59E0B` | Waarschuwingen ("prijs kan wijzigen") |
| `--color-danger` | Rood | `#E5484D` | Fouten, verwijderacties |

**Regels:** rood is uitsluitend voor fouten/verwijderen, nooit voor marketing-urgentie (geen schreeuwerige rood). Amber = het "seintje"/de positieve attentiekleur. Groen = dealstatus. Donkere modus is optioneel voor v1 (tokens zo opzetten dat dark later toe te voegen is).

### 4.2 Typografie

- **Koppen:** **Poppins** (gewichten 600, 700) — Google Fonts.
- **Body & UI/alerts:** **Inter** (gewichten 400, 500, 600) — Google Fonts.
- Laad via `next/font` (self-hosted, geen externe call → AVG-vriendelijk en snel).

**Type-schaal (desktop / mobiel):**

| Stijl | Font / gewicht | Grootte desktop | Grootte mobiel | Line-height |
|---|---|---|---|---|
| Display (hero) | Poppins 700 | 56px | 36px | 1.05 |
| H1 | Poppins 700 | 40px | 30px | 1.1 |
| H2 | Poppins 600 | 30px | 24px | 1.2 |
| H3 | Poppins 600 | 22px | 20px | 1.3 |
| Body L | Inter 400 | 18px | 17px | 1.6 |
| Body | Inter 400 | 16px | 16px | 1.6 |
| Small/caption | Inter 500 | 14px | 14px | 1.5 |
| Button/label | Inter 600 | 16px | 16px | 1 |

### 4.3 Spacing, radii, schaduw, motion

- **Spacing-schaal (px):** 4, 8, 12, 16, 24, 32, 48, 64, 96. Gebruik consequent.
- **Container:** max-breedte 1200px, zijmarge 24px (mobiel 16px).
- **Radii:** inputs/knoppen 10px, kaarten 16px, app-icoon/avatars 12px, pills/badges 999px.
- **Schaduw:** subtiel. `shadow-card`: `0 1px 2px rgba(16,42,67,.06), 0 4px 16px rgba(16,42,67,.06)`. Geen zware drop-shadows.
- **Motion:** rustig en functioneel. Transities 150–200ms ease-out. Eén speels detail: de "ping"-stip mag licht pulseren (respecteer `prefers-reduced-motion`). Geen autoplay-carousels.

### 4.4 Iconografie & beeld

- **Iconen:** `lucide-react`, lijnstijl, 1.75px stroke. Kernicoon = papieren vliegtuigje + meldingsstip (zie logo, sectie 6 merkdoc).
- **Illustratie/foto:** lichte, heldere reisfoto's (citytrips: Lissabon, Barcelona, Praag) met blauw/amber-overlay-accenten; of vriendelijke vlakke illustraties. Vermijd stockclichés van zakenreizigers. Gebruik `next/image`, lazy-load, WebP/AVIF.
- **Favicon / Telegram-avatar / app-icoon:** het beeldmerk (vliegtuigje + amber ping) op `--color-primary`, herkenbaar op 32px.

### 4.5 Kerncomponenten (te bouwen als herbruikbare library)

Bouw met **shadcn/ui** (Radix + Tailwind) waar mogelijk, plus eigen merkcomponenten:
`Button` (primary/secondary/ghost/danger), `Input`, `Select`, `MultiSelect` (vertrekvelden), `Slider`/`NumberInput` (prijsdrempel), `RangeInput` (reisduur min–max nachten), `Toggle/Switch`, `Checkbox`, `RadioGroup`, `Badge/Pill`, `Card`, `Alert/Toast`, `Modal/Dialog`, `Tabs`, `Accordion` (FAQ), `Tooltip`, `Avatar`, `Navbar`, `Footer`, `Stepper` (onboarding), `EmptyState`, `PriceTag`, `ChannelIcon` (Telegram/e-mail/WhatsApp), `PlanCard` (Free/Premium), `Skeleton`-loaders, `DealCard` (voorbeeld-alert).

---

## 5. Merkstem (voor alle copy)

**Do's:** praat als een nuchtere vriend die goed kan rekenen — kort, helder, concreet (route, retour-totaalprijs, data/reisduur, vertrekveld). Laat cijfers het werk doen. Wees transparant (altijd totaalprijs + "prijzen kunnen wijzigen"). Een tikje speels mag, nooit ten koste van duidelijkheid. Spreek met **je/jij**, actieve zinnen, één scherm = één duidelijke actie.

**Don'ts:** geen schreeuwerige clickbait (geen CAPS, geen "!!!"), geen valse urgentie/nepschaarste, geen Engels marketingjargon waar een NL-woord volstaat, geen emoji-overdaad (max. één functioneel icoon), niet beloven "altijd de laagste prijs ter wereld" — wél "automatisch onder jóuw drempel".

Alle UI-copy, e-mails, bot-berichten en foutmeldingen volgen deze stem. Microcopy-voorbeelden staan door dit document heen.

---

## 6. Aanbevolen tech stack (met motivatie)

Je vroeg om een aanbeveling — dit is een pragmatische, schaalbare keuze die Claude Code goed kan bouwen.

| Laag | Keuze | Waarom |
|---|---|---|
| Framework | **Next.js (App Router) + React + TypeScript** | Eén codebase voor SEO-vriendelijke marketingpagina's (SSG/ISR) én interactieve app (dashboard). Server Actions + Route Handlers voor API. Sterke i18n. Claude Code bouwt dit uitstekend. |
| Styling | **Tailwind CSS** + CSS custom properties | Snelle, consistente implementatie van het designsysteem via tokens. |
| Componenten | **shadcn/ui** + `lucide-react` | Toegankelijke, eigenaarschap-vriendelijke componenten (geen zware dependency). |
| Database | **PostgreSQL** (Supabase of Neon) | Relationeel model past bij users/alerts/observaties; managed hosting. |
| ORM | **Prisma** | Type-safe schema + migraties; leesbaar voor onderhoud. |
| Auth | **Auth.js (NextAuth v5)** — e-mail magic link + Google OAuth | Wachtwoordloos = minder wrijving en minder beveiligingsrisico. |
| Achtergrond/scan | **Aparte Node/TypeScript-worker** + **BullMQ** op **Redis** (Upstash) | Serverless functies zijn niet ideaal voor langlopende dagelijkse scans/fan-out; een worker + queue is robuust en schaalt per gebruiker/route. |
| Scheduler | **Cron** (worker-cron of platform-scheduler) | Dagelijkse scan + Premium near-realtime polling. |
| Flight-data | **`FlightDataProvider`-interface**, adapter voor **Kiwi Tequila** (+ mock) | Provider-onafhankelijk; zie sectie 3. |
| E-mail | **Resend** (of Postmark) | Transactionele e-mail + alert-digests, goede deliverability, eenvoudige API. |
| Telegram | **Telegram Bot API** via **telegraf** | Standaard, gratis, betrouwbaar. |
| WhatsApp (Premium) | **Meta WhatsApp Cloud API** (alt: MessageBird/Bird) | Officieel; let op per-bericht-kosten → alleen Premium. |
| Betalingen | **Mollie** (iDEAL, Bancontact, SEPA recurring) | Dé NL/BE-betaalprovider; ondersteunt abonnementen (eerste betaling iDEAL/Bancontact → daarna SEPA-incasso). |
| Hosting | **Vercel** (Next.js) + **Railway/Render/Fly.io** (worker) + **Supabase/Neon** (DB) + **Upstash** (Redis) | Lage opstartkosten, schaalt mee. |
| Analytics | **Plausible** (of Vercel Analytics) | Cookieloos/privacyvriendelijk → minder AVG-last. |
| Foutmonitoring | **Sentry** | Fouten in app + worker. |

**Alternatief als je het simpeler wilt houden:** Supabase als all-in-one (Postgres + Auth + Edge Functions + cron) en de scan als Supabase Scheduled Edge Function/queue. Houd dezelfde interfaces aan.

---

## 7. Architectuuroverzicht

```
[ Bezoeker / Gebruiker ]
        │  (HTTPS)
        ▼
┌──────────────────────────────┐        ┌─────────────────────┐
│  Next.js (Vercel)            │        │  Telegram / WhatsApp │
│  - Marketingsite (SSG/ISR)   │        │  / E-mail            │
│  - App-UI (dashboard, auth)  │◄──────►│  (notificatiekanalen)│
│  - API Route Handlers        │        └─────────▲───────────┘
└──────────┬───────────────────┘                  │
           │ Prisma                                │ verzendt
           ▼                                       │
┌──────────────────────────────┐        ┌──────────┴───────────┐
│  PostgreSQL (Supabase/Neon)  │◄──────►│  Scan-worker (cron)   │
│  users, alerts, observaties, │        │  + BullMQ / Redis     │
│  notificaties, subscriptions │        │  - haalt prijzen op   │
└──────────────────────────────┘        │  - vergelijkt drempel │
           ▲                              │  - enqueue alerts     │
           │ webhooks                     └──────────┬───────────┘
┌──────────┴───────────┐                            │ FlightDataProvider
│  Mollie (betalingen) │                            ▼
└──────────────────────┘                  ┌───────────────────────┐
                                           │ Kiwi Tequila / mock   │
                                           └───────────────────────┘
```

---

## 8. Sitemap

**Publiek (marketing):**
- `/` — Homepage
- `/hoe-het-werkt` — Hoe het werkt (3 stappen, uitgebreid)
- `/premium` — Prijzen & Premium (Free vs Premium)
- `/bestemmingen` — Voorbeeld-bestemmingen / recente deals (social proof, SEO)
- `/over-ons` — Over Vliegseintje (verhaal, vertrouwen)
- `/blog` + `/blog/[slug]` — Reistips & dealuitleg (SEO-motor)
- `/faq` — Veelgestelde vragen
- `/contact` — Contact / support

**Auth:**
- `/registreren` — Account aanmaken
- `/inloggen` — Inloggen (magic link / Google)
- `/auth/verify` — Magic-link-verificatie

**App (ingelogd, onder `/app`):**
- `/app` — Dashboard
- `/app/alerts` — Mijn alerts (lijst)
- `/app/alerts/nieuw` — Alert aanmaken (wizard)
- `/app/alerts/[id]` — Alert bewerken + geschiedenis
- `/app/kanalen` — Notificatiekanalen koppelen (Telegram/e-mail/WhatsApp)
- `/app/abonnement` — Abonnement & facturatie (upgrade/downgrade)
- `/app/account` — Profiel & instellingen
- `/app/onboarding` — Eerste-keer-wizard (kan overlay zijn)

**Legal / systeem:**
- `/privacy` — Privacyverklaring (AVG)
- `/voorwaarden` — Algemene voorwaarden
- `/cookies` — Cookiebeleid
- `/robots.txt`, `/sitemap.xml`, `404`, `500`

---

## 9. Homepage — gedetailleerd

Doel: in één scroll uitleggen wat het is, vertrouwen wekken en aanzetten tot account aanmaken. Eén primaire CTA, consequent herhaald: **"Zet mijn eerste seintje aan"** (→ `/registreren`).

**9.0 Navbar (sticky, transparant→wit bij scroll)**
Links: logo (vliegtuigje + amber ping + woordmerk "vliegseintje"). Midden: Hoe het werkt · Premium · Bestemmingen · Blog. Rechts: "Inloggen" (ghost) + "Account aanmaken" (primary). Mobiel: hamburger → drawer.

**9.1 Hero**
- Layout: tekst links, visual rechts (op mobiel gestapeld). Achtergrond wit met zachte amber/blauwe accentvorm.
- **H1 (Display):** "Goedkoop vliegen, zonder zoeken."
- **Sub (Body L):** "Stel je vertrekvelden en je maximumprijs in. Wij scannen elke dag de prijsvechters en geven je een seintje zodra er een retour onder jouw drempel duikt — via Telegram, e-mail of WhatsApp."
- **Primaire CTA:** "Zet mijn eerste seintje aan" · **secundair:** "Bekijk hoe het werkt" (scrollt naar sectie).
- **Vertrouwensregel onder CTA (Small):** "Gratis te proberen · geen creditcard · stop wanneer je wilt."
- **Visual:** een gestileerde telefoon/inbox met een voorbeeld-alert (`DealCard`): "✈️ Amsterdam → Lissabon — €38 retour · onder jouw drempel van €60". De ping-stip pulseert licht.

**9.2 Social proof / logobalk (compact)**
Korte regel: "Werkt met de vertrekvelden die jij kiest — Eindhoven, Charleroi, Brussel, Schiphol en meer." Eventueel later: aantal actieve seintjes/gebruikers (alleen tonen als waar; niet verzinnen).

**9.3 "Hoe het werkt" — 3 stappen**
Drie kaarten met icoon + korte tekst:
1. **Kies je vertrekvelden.** "Vanaf welke luchthavens wil je vertrekken? Kies er één (gratis) of meerdere (Premium)."
2. **Stel je drempel & reisduur in.** "Bijvoorbeeld: max €60 retour, 3–5 nachten."
3. **Wij geven je een seintje.** "Zodra er een retour onder je drempel duikt, krijg je bericht via Telegram, e-mail of WhatsApp."
CTA onder de stappen: "Zet mijn eerste seintje aan".

**9.4 Voorbeeld-alerts / recente deals**
Grid van 3–6 `DealCard`'s (route, prijs, data, airline, "onder drempel"-badge in groen). Mag voorbeelddata zijn in MVP, met label "voorbeeld". Later: echte recente deals uit de database. SEO-anker naar `/bestemmingen`.

**9.5 Waarom Vliegseintje (waardeproposities)**
Vier korte blokken met icoon:
- **Jij hoeft niet te zoeken** — wij scannen elke dag automatisch.
- **Jouw drempel, jouw regels** — alleen een seintje als het écht onder je maximum zit.
- **Waar je al bent** — Telegram, e-mail of WhatsApp.
- **Nuchter & transparant** — altijd de retour-totaalprijs, geen verborgen sterretjes.

**9.6 Free vs Premium (teaser)**
Twee `PlanCard`'s naast elkaar (zie sectie 11) met "Vergelijk plannen"-knop → `/premium`. Premium-kaart subtiel uitgelicht met amber-accent, niet schreeuwerig.

**9.7 Telegram-bot-blok**
Korte uitleg + visual van de bot in actie + knop "Open de Telegram-bot" (deeplink). "Liever alles in Telegram? Koppel je account aan onze bot en ontvang je seintjes direct in je chat."

**9.8 FAQ-preview**
3–4 ingeklapte vragen (`Accordion`) + link naar `/faq`. Bv.: "Is het gratis?", "Hoe snel krijg ik een seintje?", "Welke luchtvaartmaatschappijen?", "Boeken jullie de tickets?".

**9.9 Slot-CTA (band)**
Volle-breedte band in `--color-primary` met witte tekst: "Klaar voor je volgende citytrip onder de €60?" + CTA "Zet mijn eerste seintje aan".

**9.10 Footer**
Kolommen: Product (Hoe het werkt, Premium, Bestemmingen), Bedrijf (Over ons, Blog, Contact), Juridisch (Privacy, Voorwaarden, Cookies), Volg ons (Instagram/TikTok/X — handles uit merkdoc). Onderaan: logo, "© 2026 Vliegseintje", taalkeuze (NL, later BE/EN), "Prijzen onder voorbehoud; vluchten worden geboekt bij derden."

**Responsive:** mobile-first. Hero stapelt, stappen worden verticale lijst, plan-kaarten stapelen. Alles bedienbaar met toetsenbord, voldoende contrast (WCAG AA).

---

## 10. Overige publieke pagina's

**10.1 `/hoe-het-werkt`** — uitgebreide versie van de 3 stappen, met screenshots/illustraties van het instellen van een alert, uitleg verschil dagelijkse digest (Free) vs instant (Premium), welke kanalen, en een uitleg over "flexibel reizen = goedkoper". CTA's naar registreren.

**10.2 `/premium`** — volledige plannenvergelijking (sectie 11), prijs, betaalmethoden (iDEAL/Bancontact-logo's), FAQ over opzeggen/terugbetalen, "geen verborgen kosten". Eén duidelijke upgrade-CTA. Toon prijs incl. btw, in euro's.

**10.3 `/bestemmingen`** — galerij van recente/voorbeelddeals, filterbaar op vertrekveld; per stad een kort kaartje. Sterk voor SEO ("goedkoop vliegen naar Lissabon vanaf Eindhoven"). In MVP voorbeelddata; later gevuld uit `PriceObservation`.

**10.4 `/over-ons`** — het verhaal: gemaakt door en voor prijsbewuste reizigers; waarom (zelf altijd zitten zoeken naar deals); hoe we geld verdienen (Premium + affiliate, transparant); belofte over privacy. Bouwt vertrouwen — nuchter, geen grootspraak.

**10.5 `/blog` + `/blog/[slug]`** — MDX-gebaseerde blog. Indexpagina met kaarten; artikelpagina met inhoudsopgave, deelknoppen, gerelateerde posts, CTA-blok naar registreren. SEO: meta, OG-image, `Article` structured data. Voorbeeldonderwerpen: "Wanneer zijn vliegtickets het goedkoopst?", "10 citytrips onder €50 vanaf Eindhoven", "Handbagage-only slim inpakken".

**10.6 `/faq`** — gegroepeerde vragen (Algemeen, Alerts & kanalen, Premium & betalen, Privacy). `Accordion`. Schema.org `FAQPage`.

**10.7 `/contact`** — contactformulier (naam, e-mail, bericht) → e-mail naar support + opslag; verwijzing naar FAQ; responstijd-verwachting. Spam-bescherming (honeypot + rate limit).

**10.8 Legal** — `/privacy`, `/voorwaarden`, `/cookies` als MDX/CMS-content. Placeholder-teksten met duidelijke TODO's; échte juridische teksten laat Tim (laten) opstellen.

---

## 11. Free vs Premium — feature-matrix

| Functie | Free | Premium |
|---|---|---|
| Aantal vertrekvelden | 1 | Meerdere (bv. tot 10) |
| Levering | **Dagelijkse digest** (1× p/dag gebundeld) | **Instant** (zo snel mogelijk na detectie) |
| Kanalen | Telegram + e-mail | Telegram + e-mail + **WhatsApp** |
| Aantal actieve alerts | bv. 3 | bv. onbeperkt / hoog limiet |
| Prijsdrempel & reisduur instellen | ✓ | ✓ |
| Prijsgeschiedenis per alert | basis | uitgebreid |
| Prioriteit/extra airlines (later) | — | ✓ |

Exacte limieten bevestigen met Tim; bouw ze als **configuratie** (sectie 17 `PlanLimits`), niet hardcoded. Premium-prijs als placeholder (bv. €X/maand of €Y/jaar) — niet verzinnen als definitief; toon als config-waarde.

---

## 12. App — schermen (ingelogd)

Algemene app-shell: linker zijbalk (desktop) / onderbalk of drawer (mobiel) met: Dashboard, Mijn alerts, Kanalen, Abonnement, Account. Bovenin: logo, plan-badge (Free/Premium), avatar-menu (uitloggen).

**12.1 Onboarding-wizard (`/app/onboarding`)** — `Stepper`, 3–4 stappen, verschijnt direct na eerste registratie:
1. Welkom + korte uitleg.
2. **Vertrekveld(en) kiezen** (`MultiSelect` met luchthaven-zoek; Free = 1).
3. **Drempel & reisduur** (`Slider`/`NumberInput` voor max prijs; `RangeInput` voor min–max nachten; optioneel bestemmingsvoorkeur/"verras me").
4. **Kanaal koppelen** (Telegram deeplink / e-mail bevestigd / WhatsApp = Premium). Afsluiten → eerste alert is live; toon bevestiging.

**12.2 Dashboard (`/app`)** — overzicht:
- Begroeting + status ("Je hebt 2 actieve seintjes. Laatste scan: vandaag 07:00.").
- Kaarten met actieve alerts (samenvatting: vertrekveld, drempel, reisduur, kanaal, laatste resultaat).
- Recente seintjes (lijst van getriggerde alerts met prijs + link).
- Lege staat (`EmptyState`): "Nog geen seintjes — stel je eerste alert in." + CTA.
- Upgrade-hint voor Free-gebruikers (subtiel, niet pusherig).

**12.3 Mijn alerts (`/app/alerts`)** — lijst van alle alerts met aan/uit-toggle, bewerken, verwijderen. Knop "Nieuwe alert" (Free → blokkeren bij limiet met nette upgrade-uitleg).

**12.4 Alert aanmaken/bewerken (`/app/alerts/nieuw`, `/app/alerts/[id]`)** — kernscherm. Velden:
- **Vertrekveld(en)** — `MultiSelect`, zoekbaar (IATA + plaatsnaam). Free: 1.
- **Prijsdrempel** — max retour-totaalprijs in €.
- **Reisduur** — min–max nachten.
- **Reisperiode** (optioneel) — bv. "komende 6 maanden", of datumrange; "weekend / midweek / maakt niet uit".
- **Bestemmingen** (optioneel) — alles / specifieke landen-steden / "verras me".
- **Kanaal** — welke gekoppelde kanalen voor deze alert.
- **Leverwijze** — Free = dagelijks (vast); Premium = instant of dagelijks.
- Live preview ("Je krijgt een seintje zodra een retour vanaf Eindhoven onder €60 zakt, 3–5 nachten."). Opslaan → terug naar lijst.

**12.5 Alert-detail / geschiedenis** — grafiek/lijst van waarnemingen en getriggerde seintjes; "opnieuw scannen" (rate-limited); deel/aan-uit.

**12.6 Kanalen (`/app/kanalen`)** — koppel/ontkoppel:
- **Telegram:** knop genereert deeplink/koppelcode → gebruiker opent bot → `/start <code>` → gekoppeld. Toon status "gekoppeld als @handle".
- **E-mail:** standaard het account-e-mail; verifieer; aan/uit per alert.
- **WhatsApp (Premium):** opt-in flow met telefoonnummer-verificatie; duidelijk dat het Premium is en dat WhatsApp utility-berichten betreft.

**12.7 Abonnement (`/app/abonnement`)** — huidig plan, voordelen, upgrade-knop → Mollie-checkout (iDEAL/Bancontact). Toon facturen, volgende incassodatum, opzeggen (downgrade naar Free aan einde periode). Webhook-statussen netjes afhandelen (actief, openstaand, mislukt → herinnering).

**12.8 Account (`/app/account`)** — naam, e-mail, taal/regio (NL/BE), wachtwoordloos beheer (verbonden logins), notificatie-voorkeuren (globale opt-outs), **data exporteren** en **account verwijderen** (AVG). Toon land voor btw/valuta.

---

## 13. Datamodel (Prisma-schema — entiteiten & velden)

Implementeer als Prisma-models. Hieronder de essentie (voeg `id`, `createdAt`, `updatedAt` overal toe).

- **User**: `email` (uniek), `name`, `locale` (nl-NL/nl-BE), `country`, `role` (user/admin), `planId` (→ Plan), relaties: alerts, channels, subscription, sessions.
- **Account / Session / VerificationToken**: standaard Auth.js-modellen.
- **Plan**: `key` (free/premium), `name`, `priceCents`, `interval` (month/year), `limits` (JSON: maxDepartureAirports, maxAlerts, delivery: digest|instant, whatsapp: bool).
- **Subscription**: `userId`, `planId`, `mollieCustomerId`, `mollieSubscriptionId`, `status` (active/pending/past_due/canceled), `currentPeriodEnd`, `canceledAt`.
- **NotificationChannel**: `userId`, `type` (telegram/email/whatsapp), `identifier` (telegram chatId / e-mail / telefoonnr), `verified` (bool), `linkCode`, `active`.
- **Alert** (de "watch"): `userId`, `name`, `maxPriceCents`, `minNights`, `maxNights`, `travelWindowStart`, `travelWindowEnd`, `tripType` (weekend/midweek/any), `destinationMode` (any/list/surprise), `active`, `delivery` (digest/instant), relaties: departureAirports (M:N), destinations (optioneel), channels (welke kanalen).
- **Airport**: `iata`, `name`, `city`, `country`, `lat`, `lng` (seed-dataset van relevante EU-luchthavens; Ryanair/Wizz-velden).
- **AlertDepartureAirport** (join): `alertId`, `airportId`.
- **PriceObservation**: `routeFrom` (iata), `routeTo` (iata), `airline`, `priceCents`, `currency`, `departDate`, `returnDate`, `nights`, `deepLink`, `source` (provider), `observedAt`. (Bron voor /bestemmingen en geschiedenis; dedupe op route+datums+prijs.)
- **AlertHit**: `alertId`, `priceObservationId`, `priceCents`, `triggeredAt`, `notifiedAt`, `status` (pending/sent/failed/suppressed). Voorkomt dubbele meldingen (dedupe op alert + route + prijsklasse binnen venster).
- **NotificationLog**: `userId`, `channelType`, `alertHitId`, `status`, `providerMessageId`, `error`, `sentAt`.
- **ContactMessage**: `name`, `email`, `message`, `handled`.
- **BlogPost** (of via MDX-bestanden i.p.v. DB): `slug`, `title`, `excerpt`, `body`, `coverImage`, `publishedAt`, `tags`.

Indexen op: `Alert.active`, `PriceObservation(routeFrom, departDate)`, `AlertHit(alertId, triggeredAt)`, `NotificationChannel(userId, type)`.

---

## 14. API & server-acties

Gebruik Next.js Route Handlers (`/app/api/...`) en/of Server Actions. Bescherm alle app-endpoints met auth + per-user autorisatie. Validatie met **Zod**.

**Auth:** afgehandeld door Auth.js (`/api/auth/...`).

**Alerts:**
- `GET /api/alerts` — eigen alerts.
- `POST /api/alerts` — aanmaken (handhaaf planlimieten server-side).
- `GET /api/alerts/:id`, `PATCH /api/alerts/:id`, `DELETE /api/alerts/:id`.
- `POST /api/alerts/:id/test` — test-scan (rate-limited).

**Kanalen:**
- `POST /api/channels/telegram/link` — genereer koppelcode/deeplink.
- `POST /api/channels/email/verify`, `POST /api/channels/whatsapp/verify` (Premium).
- `DELETE /api/channels/:id`.

**Telegram-webhook:** `POST /api/telegram/webhook` — verwerkt `/start <code>` (koppelen), `/stop`, `/help`, `/status`.

**Betalingen (Mollie):**
- `POST /api/billing/checkout` — start eerste betaling/abonnement.
- `POST /api/billing/webhook` — Mollie-statusupdates (verifieer + idempotent).
- `POST /api/billing/cancel` — opzeggen.

**Account/AVG:**
- `GET /api/account/export` — data-export (JSON/zip).
- `DELETE /api/account` — verwijder account + cascade.

**Publiek:**
- `POST /api/contact` — contactformulier (rate-limited, honeypot).
- `GET /api/deals` — recente publieke deals voor `/bestemmingen` (gecachet).

**Intern (worker → niet publiek):** queue-jobs, geen open endpoint.

---

## 15. Scan-engine (het hart)

Aparte worker met queue. Flow:

1. **Scheduler** draait de **dagelijkse scan** (bv. 07:00 Europe/Amsterdam) en een **frequentere poll** voor Premium-instant (bv. elk uur of vaker, binnen API-limieten).
2. **Plan jobs:** verzamel actieve alerts, groepeer slim op (vertrekveld × reisparameters) om dubbele API-calls te vermijden. Enqueue per groep een `scan-job` in BullMQ.
3. **Per job:** roep `FlightDataProvider.searchReturn({ from, dateRange, minNights, maxNights, destinations })` aan. Respecteer rate limits, caching en backoff. Sla resultaten op als `PriceObservation`.
4. **Match:** vergelijk gevonden retourprijzen met de `maxPriceCents` van elke relevante alert (en reisduur/venster/bestemmingsfilters).
5. **Dedupe:** maak een `AlertHit` alleen als er nog niet recent (configureerbaar venster, bv. 24–72u) een vergelijkbare hit (zelfde route+prijsklasse) is gemeld → geen spam.
6. **Lever:** 
   - **Free:** verzamel hits en stuur **1× per dag een digest** per kanaal.
   - **Premium:** stuur **instant** per hit (met lichte throttling per gebruiker).
7. **Verzend** via de juiste `NotificationChannel`-adapters; log in `NotificationLog`; markeer `AlertHit.status`.
8. **Foutafhandeling:** retries met backoff; provider-fouten loggen naar Sentry; bij structurele blokkade alerts pauzeren en Tim waarschuwen.

**Eisen:** idempotent, herstartbaar, observeerbaar (metrics: jobs/min, hits/dag, verzendsucces). Provider-calls achter één interface; alles configureerbaar (scan-tijden, dedupe-venster, throttle).

---

## 16. Notificaties — kanalen & templates

Eén `NotificationService` met adapters per kanaal en herbruikbare, merkconforme templates.

**Telegram (telegraf):** koppelen via `/start <code>`. Berichtformaat (instant):
```
✈️ Amsterdam → Lissabon — €38 retour
Heen 14 sep · terug 18 sep (4 nachten) · Ryanair
Onder jouw drempel van €60. Prijzen kunnen snel wijzigen.
→ Bekijk de vlucht: <deeplink>
```
Commando's: `/start`, `/status`, `/stop`, `/help`.

**E-mail (Resend):** transactioneel (magic link, verificatie, betaalstatus) + **dagelijkse digest** (Free). Digest = nette HTML met 1–N `DealCard`-rijen, merkkleuren, één "Bekijk"-knop per deal, footer met "beheer je seintjes" + uitschrijflink. Onderwerp-voorbeeld: "Je seintjes van vandaag — 3 retours onder je drempel".

**WhatsApp (Premium, Meta Cloud API):** vooraf goedgekeurde **utility-template** met variabelen (route, prijs, data, link). Strikte opt-in; let op per-bericht-kosten → alleen Premium en alleen instant-hits. Respecteer opt-out.

**Algemeen:** elke melding bevat de transparantieregel "prijzen kunnen wijzigen", een werkende doorklik (affiliate-deeplink waar mogelijk), en respecteert kanaal- en globale opt-outs. Nooit 's nachts spammen (Free = ochtenddigest; Premium instant met redelijke venster-instelling, configureerbaar door gebruiker).

---

## 17. Configuratie & plan-limieten

Centrale config (env + DB `Plan.limits`):
```
FREE:    { maxDepartureAirports: 1, maxAlerts: 3, delivery: "digest", whatsapp: false }
PREMIUM: { maxDepartureAirports: 10, maxAlerts: 50, delivery: "instant|digest", whatsapp: true }
```
Handhaaf limieten **server-side** (niet alleen in de UI). Prijzen/limieten als data, niet hardcoded. Tijdzone overal `Europe/Amsterdam`. Valuta `EUR`, prijzen incl. btw tonen.

**Env-variabelen (`.env.example` opleveren):**
`DATABASE_URL`, `REDIS_URL`, `AUTH_SECRET`, `AUTH_GOOGLE_ID/SECRET`, `RESEND_API_KEY`, `TELEGRAM_BOT_TOKEN`, `WHATSAPP_*` (Meta), `MOLLIE_API_KEY`, `FLIGHT_API_KEY` (Tequila), `NEXT_PUBLIC_SITE_URL`, `PLAUSIBLE_*`, `SENTRY_DSN`.

---

## 18. Build-volgorde (fasen voor Claude Code)

**Fase 0 — Fundament:** repo, Next.js + TS + Tailwind, designsysteem-tokens (kleuren/typografie/spacing), componentbibliotheek (sectie 4.5), layout (Navbar/Footer), i18n-setup (nl-NL standaard), SEO-basis, Plausible, Sentry.

**Fase 1 — Marketingsite:** Homepage (alle secties van sectie 9), `/hoe-het-werkt`, `/premium`, `/bestemmingen` (voorbeelddata), `/over-ons`, `/faq`, `/contact`, blog (MDX), legal-pagina's (placeholders). Volledig responsive + toegankelijk. CTA's wijzen naar `/registreren`.

**Fase 2 — Auth & app-shell:** Auth.js (magic link + Google), `/registreren`, `/inloggen`, app-shell met navigatie, beschermde routes, account-pagina (incl. data-export/verwijderen-stubs).

**Fase 3 — Alerts & datamodel:** Prisma-schema + migraties, Airport-seed, alert CRUD (UI + API + Zod + planlimieten), onboarding-wizard, dashboard, kanalen-scherm (Telegram-koppeling werkend).

**Fase 4 — Backend/scan-engine:** worker + BullMQ + Redis, `FlightDataProvider` (mock + Tequila-adapter), scan/dedupe/match-logica, `NotificationService` (Telegram + e-mail digest), logging/metrics.

**Fase 5 — Premium & betalingen:** Plan/Subscription, Mollie-checkout + webhooks, instant-levering, WhatsApp-adapter, upgrade/downgrade, facturen.

**Fase 6 — Afwerking:** echte `/bestemmingen`-data, prijsgeschiedenis-grafieken, e-mail/HTML-polish, performance- en SEO-pass, AVG-afronding (cookiebanner indien nodig, consent-logica), tests, documentatie (`README`, `DECISIONS.md`).

Lever na elke fase werkende, deploybare code + korte changelog.

---

## 19. Niet-functionele eisen

**Performance:** Core Web Vitals groen; marketingpagina's SSG/ISR; afbeeldingen via `next/image` (AVIF/WebP, lazy). LCP < 2.5s op mobiel. Self-hosted fonts.

**SEO:** per pagina `title`/`meta description`/canonical/OG/Twitter-tags; `sitemap.xml` + `robots.txt`; structured data (`Organization`, `FAQPage`, `Article`); semantische headings; NL-trefwoorden ("goedkoop vliegen", "vliegdeals", "[stad] vanaf [luchthaven]"). Bloggebaseerde content-motor.

**Toegankelijkheid:** WCAG 2.1 AA — contrast, focusstates, toetsenbordnavigatie, aria-labels, `prefers-reduced-motion`, formulierlabels + foutmeldingen.

**i18n:** nl-NL als standaard, nl-BE-variant (zelfde taal, evt. "je"-toon en lokale luchthavens Charleroi/Brussel/Antwerpen); architectuur klaar voor EN/FR later. Teksten in resource-bestanden, niet hardcoded.

**AVG/GDPR:** privacyvriendelijke (cookieloze) analytics → idealiter geen cookiebanner nodig; als er wél niet-essentiële cookies komen, een correcte consent-banner (opt-in). Data-export + accountverwijdering. Privacyverklaring + verwerkersovereenkomsten met providers. Dataminimalisatie (alleen e-mail + voorkeuren). Telefoonnummer alleen bij WhatsApp-opt-in.

**Security:** HTTPS, secrets in env (nooit in repo), input-validatie (Zod), rate limiting op publieke + auth-endpoints, CSRF-bescherming, webhook-signatuurverificatie (Mollie/Telegram/WhatsApp), least-privilege DB. Geen wachtwoorden (magic link/OAuth).

**Betrouwbaarheid:** idempotente jobs, retries, dead-letter queue, monitoring/alerting op scan- en verzendfouten. Transparantie naar gebruiker als een scan faalt.

**Juridisch/affiliate:** doorkliklinks bij voorkeur affiliate; duidelijke disclaimer "vluchten geboekt bij derden, prijzen onder voorbehoud"; respecteer voorwaarden van de databron (zie sectie 3).

---

## 20. KPI's & analytics-events

Meet (privacyvriendelijk): bezoek → registratie-conversie, onboarding-voltooiing, alerts-per-gebruiker, kanaal-koppelpercentage, alert→klik-ratio, Free→Premium-conversie, churn. Events o.a.: `signup`, `onboarding_completed`, `alert_created`, `channel_linked`, `alert_hit_sent`, `alert_clicked`, `upgrade_started`, `upgrade_completed`.

---

## 21. Open beslissingen voor Tim (niet door Claude Code verzinnen)

1. **Databron** definitief kiezen (Tequila/Travelpayouts/Duffel/…) + voorwaarden & kosten checken; bevestig dat directe Ryanair-scraping vermeden wordt.
2. **Premium-prijs** en exacte **plan-limieten** (vertrekvelden, alerts, scan-frequentie instant).
3. **Bedrijfsgegevens** voor legal/btw (eenmanszaak/bv, KvK, btw-nummer) en wie de juridische teksten levert.
4. **WhatsApp**: akkoord met per-bericht-kosten en Meta-onboarding (business-verificatie).
5. **Merk-handles & domeinen** vastleggen (uit merkdoc): vliegseintje.nl + .com + .app, social handles, Telegram-botnaam `@vliegseintje_bot`.
6. **Definitieve scan-tijden** en notificatievensters (rustige uren).

---

*Einde spec. Houd dit document leidend; noteer afwijkingen en aannames in `DECISIONS.md`.*
