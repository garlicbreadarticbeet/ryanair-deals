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

**Open voor Tim (uit de onderzoekschecklist):** EU-sanctiecheck van Go Travel Un Limited; en de
merk-/PR-afweging rond de Russische oorsprong (Aviasales). Verdien breder dan vluchten
(hotels/verzekering/eSIM via hetzelfde account) — flight-commissie is structureel laag.

**Implementatie (gebouwd 19-06-2026):** route-test bevestigd (`scripts/probe_travelpayouts.py`,
~100% dekking, Ryanair+Wizz aanwezig). De adapter `app/providers/travelpayouts.py` haalt retours
op via het gecachte `prices_for_dates`-endpoint. Omdat de cache **retour-native** is, is er een
optioneel `ReturnFareProvider`-pad toegevoegd (`base.ReturnFare` + `scan.run_scan`): zulke bronnen
leveren direct retours i.p.v. enkele-richting `DailyFare`s; `combine`/`match`/`notify` blijven
ongemoeid. De affiliate-deeplink (marker) + maatschappij worden opgeslagen op `deals`
(migratie 0004) en getoond in de Telegram/e-mail-alert. Nieuwe origins koppelen aan
`DEFAULT_ORIGIN_PROVIDER` (default `travelpayouts`); de Ryanair-adapter blijft als legacy/config-bron.
Prijzen zijn indicatief → de "vanaf €X, prijzen kunnen wijzigen"-UX dekt dat af.

## D7 — Niet in deze ronde
Geen native apps, geen prijsvoorspelling — conform de niet-doelen (§2). Analytics (Plausible) en
Sentry zijn als **opt-in via env** voorzien (script alleen geladen als de env-var gezet is), niet
verplicht aangezet.

## D9 — WhatsApp geschrapt (kanaal én premium-feature)
WhatsApp is **volledig verwijderd** als bezorgkanaal en als premium-feature. **Waarom:** de
WhatsApp Cloud API rekent **per bericht** (drukt de marge op een prijs-alert-product) en vereist
**KvK-/Meta-bedrijfsverificatie** die we (nog) niet hebben. De kosten/baten en de drempel wegen
niet op tegen Telegram + e-mail, die gratis en direct bruikbaar zijn.

Verwijderd: `app/channels/whatsapp.py` + registratie, de `whatsapp_*`-settings, de
`channel:whatsapp`-default in `PREMIUM_ONLY_FEATURES` (nu `mode:instant`), de koppelflow op
`/channels`, en alle UI-/content-/legal-teksten. **Behouden:** de Notifier-/kanaal-abstractie
(`app/channels/base.py`) blijft intact zodat een nieuw kanaal nog steeds één nieuw bestand is; de
core-purity-test bewaakt dat `core/` kanaalnaam-vrij blijft. Premium-features zijn daarmee:
**instant alerts + meerdere vertrekvelden + uitgebreide prijsgeschiedenis**; kanalen voor iedereen:
**Telegram + e-mail**.

## D10 — Betaalprovider: Lemon Squeezy (Merchant of Record) als start, Mollie als latere optie
Om **vandaag te kunnen innen zonder KvK** kiezen we **Lemon Squeezy** als startprovider: zij zijn
**Merchant of Record** (de juridische verkoper) en regelen de EU-btw/afdracht. Mollie vereist een
ingeschreven onderneming en wordt de **latere optie** na KvK-inschrijving.

Daarom een dunne **billing-provider-abstractie** (`app/billing_providers/`, in dezelfde geest als
`providers/` en `channels/`): `app/billing.py` is een provider-agnostische service die op
`BILLING_PROVIDER` (`lemonsqueezy`/`mollie`) de juiste provider kiest, de `subscriptions`-rij
beheert en de tier op **één plek** op-/afschaalt (`upgrade`/`downgrade`). De `subscriptions`-tabel
is provider-agnostisch gemaakt (`provider`, `external_customer_id`, `external_subscription_id`,
`plan`; migratie 0005). De Lemon Squeezy-webhook verifieert `X-Signature` (HMAC-SHA256 over de
rauwe body) en schaalt `users.tier` bij; opzeggen laat de toegang doorlopen tot einde periode
(afschalen pas bij `expired`). Het Mollie-pad blijft volledig werkend en getest.

**Prijzen (vast, uit config):** maandplan **€ 2,99**, jaarplan **€ 24,99** (≈ € 2,08/maand,
~30% goedkoper — "ruim 3 maanden gratis"). Het jaarplan staat als aanrader uitgelicht. De
besparing/maandprijs wordt **berekend** uit de config (`settings.premium_pricing`), niet hardcoded
in de templates, zodat het klopt als de prijs ooit wijzigt.

## D11 — Betere alerts: dealscore (prijsgeschiedenis) + gebrande presentatie
De alerts (Telegram + e-mail) zijn het product; daarom drie samenhangende verbeteringen.

**1. Dealscore uit prijsgeschiedenis.** Nieuwe tabel `deal_price_points` (migratie 0006) houdt
per route per dag de **laagste** retour-totaalprijs bij (gehaakt in de scan). Daaruit berekent
`app/core/scoring.py` (puur) hoe goed een prijs is t.o.v. normaal: het kortingspercentage t.o.v.
de **mediaan** over een venster en of het de **laagste in N dagen** is. Alerts ranken nu op
**dealsterkte** (spannendste eerst) i.p.v. alleen absolute prijs. Dit voedt meteen de
premium-feature "uitgebreide prijsgeschiedenis". De score **warmt op** over enkele dagen
historie; tot die tijd valt de badge terug op de per-gebruiker "was €X".

**2. Eén presentatielaag.** `app/alerts/` (verrijking + gedeelde render-helpers) zorgt dat
Telegram, e-mail én de dealkaart hetzelfde tonen: **stadsnamen + vlag** i.p.v. IATA-codes, de
**dealscore-badge** ("🔥 38% onder normaal" / "laagste in 42 dagen" / "was €X") en een nette
boekknop. De e-mail is een **gebrande, responsive HTML-mail** (tabellen + inline CSS in de
merkkleuren). Bewust buiten `core/` (UI/merk) en buiten `channels/` (kanaal-agnostisch).

**3. Merk-dealkaart (PNG).** `app/alerts/card.py` tekent met **Pillow** een gebrande kaart
(self-hosted merk-TTF's, gebundeld onder `app/alerts/assets/fonts/`) als **Telegram-foto** en
**mail-hero**. De mail-hero laadt via een **ondertekende** `/cards/deal.png`-endpoint
(`ALERT_CARD_SECRET`); zonder secret of zonder Pillow valt alles **schoon terug** op de
HTML/tekst zonder beeld (nooit een harde fout op een alert). Geen emoji in het beeld (Latijnse
fonts) — de punch komt van kleur, de grote prijs en de amber pill. Per run capt de dispatcher
op **12** deals zodat het een gerichte "top-deals"-melding blijft; de rest volgt een volgende run.

## D12 — Databron: terug naar Ryanair-direct (cheapestPerDay), Travelpayouts als latere optie
**Herziening van D8.** D8 koos de Travelpayouts cached Data API als startbron (gratis, dekt
Ryanair + Wizz, levert affiliate-deeplinks). In de praktijk bleken die prijzen **te zwak**: een
live vergelijking op de productieserver (20-06-2026, vertrekveld EIN) gaf via Travelpayouts een
goedkoopste retour van **€96** (gemiddeld €166), terwijl **Ryanair's eigen `cheapestPerDay`**
(via de bestaande `app/providers/ryanair.py`-adapter, ryanair-py) op dezelfde server **€37**
(Londen), €54 (Reus), €57 (Pisa) vond. De cache is geaggregeerd/verouderd; geen enkele 3rd-party
cache verslaat de airline-bron zelf. Een prijs-alert-product staat of valt met scherpe deals.

**Besluit:** Ryanair-direct wordt de **productiebron** (`DEFAULT_ORIGIN_PROVIDER=ryanair`).
Ryanair's API werkt prima vanaf de Hetzner-server (geen IP-blokkade — getest, 38 routes vanaf
EIN). De boekknop linkt **rechtstreeks naar ryanair.com** (de adapter bouwt een deeplink met
route + datums + retour vooringevuld via `booking_url`), zodat de getoonde prijs en de
landingspagina kloppen — **eerlijk en transparant**, conform de merkstem. Geen
affiliate-commissie voor nu: het verdienmodel is **premium-abonnementen** (D10), en commissie op
zwakke deals die niemand boekt is ~€0 waard.

De **Travelpayouts-adapter blijft bestaan** (selecteerbaar via `DEFAULT_ORIGIN_PROVIDER`/per
origin) als latere optie voor **Wizz-dekking + affiliate** waar die wél scherp is — een
mogelijke fase-2-uitbreiding (beide bronnen combineren). De scan-architectuur (provider-registry,
DailyFare- vs ReturnFare-pad) maakt zo'n omschakeling een config-/datakwestie, geen herbouw.
