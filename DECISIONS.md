# DECISIONS — Vliegseintje website

Aannames en afwijkingen t.o.v. `Website-Plan-Vliegseintje.md`, zoals gevraagd in dat plan
("noteer aannames in `DECISIONS.md`").

## D1 — Stack: Python/FastAPI/Jinja i.p.v. Next.js (bewust)
Het bouwplan (sectie 6) adviseert Next.js + React + Prisma. De codebase is echter al een
volwaardige **Python**-dienst (FastAPI + Jinja2 + SQLAlchemy + Alembic) met een bewezen,
geteste scan→match→notify-kern, en de website is daarop **server-rendered** gebouwd (commits
"Fase W1–W4"). Een Next.js-herbouw zou die werkende, geteste kern weggooien en twee codebases
opleveren.

**Besluit:** het websiteplan wordt uitgevoerd *binnen de bestaande Python-stack*. We volgen de
**inhoud** van het plan (sitemap §8, paginaspecs §9–§12, designsysteem §4, merkstem §5, SEO/AVG
§19) één-op-één; alleen de technologie (§6) wijkt af. shadcn/Tailwind worden vertaald naar een
handgeschreven designsysteem in `app/web/static/style.css` (CSS custom properties = de tokens uit §4.1).

## D2 — Merknaam: Vliegseintje (UI), techniek blijft "goedkoopvliegen"
Merkidentiteit + plan kiezen **Vliegseintje** met tagline **"Goedkoop vliegen, zonder zoeken."**
De UI is hierop omgezet. Back-end-identifiers die al live zijn (Telegram-bot
`@goedkoopvliegen_bot`, env-namen, cookienaam `gv_session`, e-mailafzender) blijven ongewijzigd om
niets te breken. Merknaam/tagline staan centraal in `settings` (`brand_name`, `brand_tagline`) zodat
ze op één plek te wijzigen zijn.

## D3 — Fonts self-hosted (AVG)
Poppins (600/700) + Inter (400/500/600) zijn als `woff2` gebundeld onder
`app/web/static/fonts/` en via `@font-face` geladen — geen externe Google-call (AVG, §19).

## D4 — Databron & prijzen: niets verzonnen
Voorbeeld-deals op `/` en `/bestemmingen` zijn **expliciet gelabeld als voorbeeld**
(`app/web/content/destinations.json`), geen live claims. De echte databron-keuze (Tequila/
Travelpayouts/…) en de definitieve premium-prijs/limieten blijven open beslissingen voor Tim
(plan §21) en zijn als **config** opgezet, niet hardcoded.

## D5 — Blog & legal als content-bestanden
Blog = Markdown met frontmatter onder `app/web/content/blog/`, gerenderd met `markdown`
(toegevoegd aan `requirements.txt`). Legal-pagina's (`privacy`/`voorwaarden`/`cookies`) zijn
**placeholder-concepten** onder `app/web/content/legal/` met duidelijke `[TODO]`-markeringen;
echte juridische teksten laat Tim opstellen/controleren (plan §10.8, §21.3).

## D6 — Contactformulier
`/contact` slaat berichten op in een nieuwe tabel `contact_messages` (migratie 0003) en mailt
support (Resend, indien geconfigureerd). Spam-beperking: honeypot-veld + eenvoudige in-memory
rate-limit per IP.

## D8 — Databron: Travelpayouts cached Data API (start), Skyscanner als groeidoel
Na onderzoek (`Vliegseintje_vluchtdata-bron_advies.md`, 19-06-2026): start met de
**Travelpayouts/Aviasales cached Data API + affiliate-deeplinks** — gratis, self-serve, dekt Ryanair
én Wizz, en levert direct affiliate-inkomsten op de doorklik. **Skyscanner** is het strategische
groeidoel (betere data + affiliate, 30-dagen cookie) zodra we ~100k MAU halen.

**Harde architectuurregel:** de dagelijkse scan draait UITSLUITEND op **cached/indicatieve** endpoints
(Travelpayouts Data API). Live-search-API's (Skyscanner Live Pricing, Travelpayouts real-time Search)
verbieden geautomatiseerd bevragen ("each search must be user-initiated") → verboden vanuit de cron.
De bestaande `ryanair`-adapter (directe `cheapestPerDay`) blijft als legacy/dev-bron maar wordt **niet**
de productiebron (plan §3 + onderzoek).

**UX-gevolg:** prijzen zijn indicatief → tonen als "vanaf €X, prijzen kunnen wijzigen" (sluit aan op de
bestaande transparantieregel); de gebruiker bevestigt op de airline/OTA via de affiliate-link.

**Open voor Tim (uit de onderzoekschecklist, vóór we de adapter afbouwen):** route-test met gratis token
(`scripts/probe_travelpayouts.py`) → dekken jouw EIN/NRN/BRU/CRL/AMS-routes?; EU-sanctiecheck van Go
Travel Un Limited; en de merk-/PR-afweging rond de Russische oorsprong (Aviasales). Verdien breder dan
vluchten (hotels/verzekering/eSIM via hetzelfde account) — flight-commissie is structureel laag.

## D7 — Niet in deze ronde
Geen native apps, geen echte WhatsApp-verzending (stub blijft), geen prijsvoorspelling — conform
de niet-doelen (§2). Analytics (Plausible) en Sentry zijn als **opt-in via env** voorzien (script
alleen geladen als de env-var gezet is), niet verplicht aangezet.
