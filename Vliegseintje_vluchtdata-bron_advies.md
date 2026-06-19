# Vliegseintje — Welke vluchtdata-bron? (beslis-klaar advies)

*Onderzoek uitgevoerd en geverifieerd bij primaire bronnen op 19 juni 2026. Markt NL/BE, valuta EUR.*

---

## TL;DR — de aanbeveling

**#1 om mee te starten: Travelpayouts (Aviasales) — gratis cached Data API + affiliate-deeplinks.**
Het is de enige bron die je vandaag zelf (self-serve, gratis) kunt aanzetten, die Ryanair én Wizz dekt, en die meteen een verdienmodel meelevert. De prijs: de data is *indicatief/gecached* (geen live fares) en de Russische oorsprong is een merk-/PR-afweging. Test daarom eerst je eigen routes voordat je commit.

**#2 als strategisch doel naarmate je groeit: Skyscanner.** Beste datakwaliteit, laagste juridische risico, directe Ryanair-deal (sept 2025) en het beste affiliate-programma (30-dagen cookie). Maar de échte fare-API zit achter een drempel van **100.000 maandelijkse gebruikers** — onbereikbaar bij de start.

**Niet doen (nu):** Kiwi Tequila (sinds 2024 alleen op uitnodiging + financiële problemen), Duffel (geen Ryanair/Wizz, boekings-API i.p.v. zoek-API), Amadeus (Self-Service stopt **17 juli 2026** + geen prijsvechters), alle RapidAPI-"flight API's" (ongelicentieerde scrapers), SerpApi (Google-rechtszaak dec 2025).

> ### Het belangrijkste inzicht — lees dit eerst
> Je aanname "we bevragen prijzen dagelijks geautomatiseerd" botst met de voorwaarden van vrijwel élke gelicentieerde *live*-API. Skyscanner Live Pricing: *"Automated requests (calls without user action) do not occur."* Travelpayouts real-time Search API: *"each search query must be initiated by the user."* **Geautomatiseerd dagelijks scannen mag legaal alléén via *cached/indicatieve* prijs-endpoints, niet via live-zoek-endpoints.** Dat is de architectuur waar je omheen moet bouwen — en precies waarom Travelpayouts' cached Data API (die expliciet bedoeld is om te cachen en te herbevragen) je realistische startpunt is.

---

## Vergelijkingstabel (kandidaten × 7 criteria)

| Kandidaat | 1. Juridisch / ToS (alert + cachen + dagelijks + doorlinken) | 2. Dekking Ryanair/Wizz vanaf EIN/NRN/BRU/CRL/AMS | 3. API (flex-date/cheapest-per-day/retour, deeplinks, limits) | 4. Kosten & test-tier (~enkele 1000 calls/dag) | 5. Verdienmodel | 6. Betrouwbaarheid/levensduur 2026 | 7. Onboarding |
|---|---|---|---|---|---|---|---|
| **Travelpayouts / Aviasales (Data API)** ✅ | **Toegestaan.** Cachen wordt *aangeraden*; alert-use is voorzien (eigen `alert`-marker); doorlinken = het kernmodel. Voorwaarden mogen wel zonder aankondiging wijzigen (§7.1). | **Ja, beide** — Aviasales-metasearch neemt LCC's mee. Maar: data komt uit zoekgeschiedenis van andere users (48u-venster) → dunne routes (NRN, EIN laagseizoen) kunnen leeg/oud zijn. **Zelf testen.** | cheapest-per-day, kalender/maand, **retour** (`prices_for_dates`, `return_at`), prijsband-zoek (`search_by_price_range` → past op je drempel-logica). Deeplinks **mét jouw affiliate-marker**. Rate limits royaal (600/min). **Prijzen standaard in RUB — `currency=eur` verplicht meegeven.** | **€0.** Geen per-call of maandkosten. Data API = gratis, alleen affiliate-account nodig. | **Ja (kernsterkte).** 40% rev-share = **~1,1% van ticketprijs** (eCPC ~$0,12, gem. ticket $353), 30-dagen cookie, NL/BE + EUR-uitbetaling oké (PayPal $50 / bank €400 min.). Flight-commissie is dun → stapel hotels/verzekering/eSIM erbij. | Actief (ToS bijgewerkt 28-11-2025). **Russische oorsprong** (Aviasales); juridische entiteit = Go Travel Un Limited, Hongkong. Geen sancties gevonden, maar merk-/PR- en bankrisico afwegen. | Self-serve, gratis, ~direct. Token meteen na registratie; Aviasales-programma auto-toegekend. |
| **Skyscanner** 🟡 | Affiliate-tier: doorlinken = kernmodel, *"mag niet boeken namens klant"* (past!). **Live Pricing-API verbiedt geautomatiseerd bevragen.** Cachen/alerts contractueel, niet publiek → bij onboarding bevestigen. Laagste juridische risico (gelicentieerde metasearch). | **Ja, beide; sterkste dekking.** **Directe Ryanair-content sinds 11-09-2025** (volledige fare + bagagekosten, boeken via deeplink). Wizz via metasearch-netwerk. Alle 5 velden gedekt. | Indicative Prices = cached, flexibele datums/cheapest-per-day (geschikt voor monitoring). Live Prices = alleen user-initiated. Affiliate Link API met attributie. **Maar: de fare-API zelf vereist 100k MAU.** | **Affiliate = gratis** (rev-share). **Maar de échte Travel/Flights-API is gated op ≥100.000 MAU** + handmatige goedkeuring → niet beschikbaar bij start. Affiliate-tier geeft alleen links/banners/zoekformulier, **geen ruwe prijsdata**. | **Ja, beste affiliate.** Rev-share via Impact.com, **30-dagen cookie**, NL/BE oké. Exacte % per partner (niet publiek; indicatie 20–50% van Skyscanner-commissie). | Zeer actief & groeiend (MCP-server, Ryanair-deal). Sterkste levensduur-signaal van alle kandidaten. | Affiliate: aanvraag via Impact.com, ~paar werkdagen, **≥5.000 bezoekers/mnd + live site vereist**. Travel API: pas bij ~100k MAU. |
| **Kiwi.com Tequila** 🔴 | Granulaire ToS niet te verifiëren (achter login). | Ryanair = officiële partner (geen scraping, live 28-05-2024). **Wizz = geen partner → waarschijnlijk gescrapet (risico).** | Retour/multicity/Nomad bestaan; rate limits/caching niet publiek te verifiëren. Deeplinks zitten in de nu-gesloten affiliate-tools. | **Niet self-serve.** Sinds **30-05-2024 alleen op uitnodiging** voor nieuwe partners. Prijs B2B-onderhandeld, niet verifieerbaar. | Direct affiliate dicht; enige route = via Travelpayouts (3% CPA, 30-dagen cookie). | **Rode vlaggen:** 250 ontslagen (29-01-2026, 2e ronde), jaren verlies; United-rechtszaak (19-08-2025, "afpersing"/scraping); eerder Southwest-injunctie. | Alleen op uitnodiging; geen garantie voor een kleine startup. |
| **Duffel** 🔴 | Boekings-API. "Fair use" Search-to-Order-ratio 1500:1, daarboven $0,005/zoekopdracht + **schorsingsrisico**; **metasearch expliciet verboden**; offers verlopen ~30 min. Slecht passend voor een scan-/alert-product. | **Nee — Ryanair én Wizz staan níét op Duffels airline-lijst.** Wel easyJet, Transavia, Vueling, KLM, e.a. NRN/CRL (Ryanair/Wizz-velden) ≈ niet gedekt. | Geen flex-date/maand-zoek (alleen offer-request per exacte datum → fan-out). Retour wel. Rate limit 120/min. | Gratis sandbox (**nepprijzen** tot KYC). Model: $3/boeking, 1% managed content, $2/ancillary, 2% FX, + excess-search-fee. Bij veel zoeken/weinig boeken: snel honderden $/mnd + schorsingsrisico. | **Geen affiliate.** Wél marge mogelijk als boekings-backend; lage regeldruk via Managed Content (Duffel = agent of record, geen eigen IATA). | Actief & onderhouden (agreement 04-2026). | Self-serve + KYC-verificatie voor live; deposit voor betalingen. |
| **Amadeus Self-Service** 🔴 | n.v.t. (geen toegang meer). | **Nee** — GDS-content, geen prijsvechters (Ryanair/Wizz ontbreken). | Cheapest-Date-Search bestaat, maar zonder LCC's. | Gratis test-quota, daarna per-call — **maar portal wordt 17-07-2026 ontmanteld, registratie nu al gepauzeerd.** | Geen affiliate (betaalde data-API). | **Self-Service stopt 17-07-2026.** Alleen Enterprise (contract) blijft. | Nieuwe self-serve-aanmelding gesloten. |
| **RapidAPI "flight API's"** (Sky-Scrapper, flights-sky, google-flights2, e.a.) 🔴 | **Ongelicentieerde scrapers** → ToS-breuk (Ryanair v PR Aviation; Google/Skyscanner ToS). | Variabel; erven scraped-data (vaak juist zwak op accuratesse). | Wisselend; breekt als de gescrapete site verandert. | Freemium, paar $–honderden $/mnd; exacte tarieven niet te verifiëren. | Geen affiliate. | Fragiel, geen garantie. | Direct, maar af te raden. |
| **SerpApi (Google Flights)** 🔴 | Scrapet Google Flights. **Google klaagde SerpApi aan op 19-12-2025** (lopend). | Ja (via Google Flights). | Goed (price graph/grid, retour). Geen affiliate-link. | Credits: $25/1k → $275/30k zoekopdrachten; jouw schaal → custom/Enterprise. | Geen affiliate. | Continuïteitsrisico door rechtszaak. | Direct, maar af te raden. |
| **Officieel Ryanair / Wizz** 🔴 | — | — | — | — | **Ryanair: geen affiliate, geen self-serve feed** — alleen "Approved OTA (Aggregator)"-contracten (Paxport, Travelfusion, Atlas, DerbySoft). **Wizz: alleen via Kyte (B2B/corporate, dec 2025).** | — | Niet realistisch voor een kleine NL/BE alert-startup. |
| **Travelfusion / Kyte / AirGateway** 🔴 | Gelicentieerd, sanctie-proof (Ryanair-Approved Aggregators). | **Ja, beide** — schoonste legale Ryanair+Wizz-bron. | Boekings-/ticketing-pipe, geen consumenten-cheapest-calendar, geen affiliate. | B2B-contract, geen publieke prijs; (AirGateway: IATA-accreditatie nodig). | Geen affiliate; je wordt sub-OTA. | Stabiel. | Contract-grade B2B; pas relevant als je zelf boekt. |

Legenda: ✅ aanrader nu · 🟡 strategisch doel · 🔴 nu niet geschikt.

---

## Top-3 met onderbouwing

### 🥇 #1 — Travelpayouts (Aviasales): cached Data API + affiliate-deeplinks
**Waarom #1:** het is de enige optie die *alle* startvoorwaarden tegelijk haalt — legaal, vandaag self-serve aan te zetten, gratis, dekt Ryanair én Wizz, en levert meteen affiliate-inkomsten op de doorklik. Het is bovendien de enige gelicentieerde bron waarvan de voorwaarden geautomatiseerd dagelijks cachen/herbevragen *expliciet toestaan* (de andere live-API's verbieden dat).

**De eerlijke nadelen (niet wegpoetsen):**
- **Data is indicatief/gecached** (tot 7 dagen oud, gevoed door zoekgeschiedenis van andere users in een 48u-venster), niet live. Voor dunne routes (NRN, EIN laagseizoen) kan data ontbreken. → Werkbaar voor een MVP met de UX "vanaf €X — check de actuele prijs", maar je moet je eigen routes eerst empirisch testen.
- **Russische oorsprong** (Aviasales). Geen sancties gevonden, maar weeg het merk-/PR-effect voor een NL/BE-consumentenmerk en mogelijke bankfrictie.
- **Dunne flight-commissie** (~1,1% van een al lage LCC-ticket → soms €0,50–€1 per boeking). Echte marge komt van hotels/verzekering/eSIM/auto die je via hetzelfde account erbij linkt.

**Geschatte maandkosten bij kleine schaal:** **€0** (geen per-call- of maandkosten; enkele duizenden calls/dag valt ruim binnen de limieten van 600/min).

**Concrete aanmeldstappen:**
1. Registreer gratis op travelpayouts.com → je wordt automatisch in het Aviasales-programma geplaatst.
2. Haal je **API-token** op (Profiel → API token) — direct beschikbaar voor de Data API.
3. Pak je **affiliate-marker** (Partner ID) voor de deeplinks.
4. Bouw de dagelijkse scan op `prices_for_dates` / `search_by_price_range` met **`currency=eur`** en de juiste `market`.
5. Doe vóór elke commitment een 2-weken-test op EIN/NRN/BRU/CRL/AMS (zie checklist).

### 🥈 #2 — Skyscanner (strategisch doel, gefaseerd)
**Waarom #2 en niet #1:** kwalitatief de beste keuze — directe Ryanair-content (sinds 11-09-2025), beste affiliate (30-dagen cookie via Impact), laagste juridische risico, sterkste levensduur. **Maar de ruwe fare-API zit achter ≥100.000 MAU.** Het affiliate-tier (≥5.000 bezoekers/mnd) geeft alleen links/widgets, geen ruwe prijsdata om je eigen alerts op te draaien. Daarom kun je er je product *nu* niet op bouwen.

**Plan:** zodra je een live site met traffic hebt → meld je aan voor het **affiliate-programma** (gratis, via Impact.com) om de doorklik beter te verzilveren dan via Travelpayouts. Richt je op de **Travel API** pas richting ~100k MAU; bouw je monitoring dan op het **Indicative Prices**-endpoint (cached, mag wél geautomatiseerd), niet op Live Pricing.

**Geschatte maandkosten:** affiliate = €0 (rev-share). Travel API = contract (geen publieke prijs).

### 🥉 #3 — Kiwi.com Tequila (alleen monitoren, niet bouwen)
De enige gelicentieerde LCC-fare-API met sterke Ryanair-dekking (en virtual interlining), maar **sinds mei 2024 alleen op uitnodiging** en met serieuze bedrijfsrisico's (ontslagrondes, United-rechtszaak). Niet als fundament bouwen. Als je Kiwi-content wilt, loopt dat realistisch via het **Kiwi-affiliate-aanbod binnen Travelpayouts** (3% CPA, 30-dagen cookie) — wat #1 en #3 samenvoegt.

---

## Wat dit praktisch betekent voor je architectuur

1. **Data-laag en verdien-laag zijn gescheiden.** Geen enkele bron doet beide perfect. Start met Travelpayouts voor *beide*, en voeg later Skyscanner-affiliate toe als sterkere verdien-laag op de doorklik.
2. **Scan op cached/indicatieve endpoints, nooit op live-search vanuit een cron.** Dat is zowel de legale als de praktische route.
3. **Toon prijzen als indicatief** ("vanaf €X, check live prijs") en laat de gebruiker op de airline/OTA bevestigen. Dat verlaagt je juridische blootstelling (je herpubliceert geen harde Ryanair-fare; je verwijst door) en dekt het cached-data-risico af.
4. **Verdien breder dan vluchten.** Vluchtcommissie is structureel laag; hotels/verzekering/transfer via hetzelfde affiliate-account leveren het echte geld op.
5. **Duffel = optionele toekomst** als je ooit zélf marge op tickets wilt pakken — maar alléén voor niet-Ryanair/Wizz-carriers (KLM, Transavia, easyJet) en mét regeldruk (agent of record, support, chargebacks).

---

## Checklist: dit moet Tim zélf bij de provider bevestigen vóór commitment

**Travelpayouts (vóór je hierop bouwt):**
- [ ] **Routetest:** haal een gratis token en query `prices_for_dates` (currency=eur, juiste market) voor **EIN, NRN, BRU, CRL, AMS** → retour naar 8–10 typische Ryanair/Wizz-bestemmingen. Meet: (a) is er data? (b) hoe vers (`expires_at`)? (c) landt de `link` op de airline of op een OTA met opslag?
- [ ] Bevestig schriftelijk dat een **prijsalert-dienst die observaties opslaat** is toegestaan (de help-center-artikelen suggereren ja; krijg het bevestigd want §7.1 staat eenzijdige wijziging toe).
- [ ] Check **Go Travel Un Limited** tegen de actuele EU-sanctielijst (EU Sanctions Map) — dit kon ik niet positief afvinken.
- [ ] Bevestig actuele **uitbetaalmethoden voor NL/BE** (PayPal $50 / bank €400; Payoneer staat niet meer in de actuele lijst).
- [ ] Beslis bewust over de **Russische-oorsprong**-afweging (merk/PR + bankrails).

**Skyscanner (vóór je erop migreert):**
- [ ] Bevestig dat **caching + prijsalert-gebruik** contractueel mag op de Travel API (niet publiek geregeld).
- [ ] Bevestig de actuele **MAU-drempel** (≥100k) en of er een startup-route is.
- [ ] Vraag de **exacte affiliate-commissie %** op in het Impact-dashboard na goedkeuring.
- [ ] Verifieer of **Wizz** via deeplink op de airline of op een OTA landt.

**Algemeen / officieel:**
- [ ] Herbevestig dat **Ryanair** geen affiliate/self-serve feed aanbiedt (alleen Approved-OTA-contracten) en **Wizz** alleen via Kyte (B2B) — zodat je geen tijd verliest aan de officiële route.
- [ ] Laat een jurist (NL/BE) kort kijken naar **herpublicatie van fares + doorlinkmodel** en of je onder consumenten-/pakketreisregels valt zodra je ooit zelf betalingen/marge pakt.

---

## Bronnen (primair, geraadpleegd 19 juni 2026)

**Travelpayouts / Aviasales**
- Voorwaarden affiliate-netwerk (bijgewerkt 28-11-2025): support.travelpayouts.com/hc/en-us/articles/360004162111
- Aviasales Data API + caching-/rate-regels: support.travelpayouts.com/hc/en-us/articles/203956163 ; .../4402565416594
- Aviasales-affiliate (40% rev-share, ~1,1% per ticket, eCPC $0,12, gem. ticket $353): travelpayouts.com/en/offers/aviasales-affiliate-program/
- Real-time Flights Search API (≥50k MAU, user-initiated, 9%/5% conversie; nieuw vanaf 01-11-2025, oud stopt 15-06-2026): support.travelpayouts.com/hc/en-us/articles/210995808
- Uitbetalingen: support.travelpayouts.com/hc/en-us/articles/206635007

**Skyscanner**
- Affiliate-programma (≥5.000 bezoekers, "geen boeken namens klant", 30-dagen cookie): partners.skyscanner.net/product/affiliates
- Travel API-toegang (≥100k MAU, handmatige goedkeuring): partners.skyscanner.net/product/travel-api
- Usage Guidelines (geen geautomatiseerde Live-Pricing-calls): developers.skyscanner.net/docs/getting-started/usage-guidelines
- Ryanair–Skyscanner-partnerschap (11-09-2025): corporate.ryanair.com/news/ryanair-announces-partnership-with-skyscanner/

**Kiwi.com**
- Tequila alleen op uitnodiging (30-05-2024): media.kiwi.com/articles-and-interviews/better-for-business-kiwi-com-takes-a-new-approach-to-partnerships/
- Ryanair-partnerschap (geen scraping): corporate.ryanair.com/news/ryanair-agrees-new-partnership-deal-with-ota-kiwi-com/
- Ontslagronde 250 banen (29-01-2026): altexsoft.com/travel-industry-news/second-layoff-kiwi-cuts-250-jobs-to-stabilize-finances/
- United-rechtszaak (19-08-2025): paddleyourownkanoo.com/2025/08/19/united-airlines-accuses-popular-travel-site-kiwi-com-of-extortion-in-explosive-new-lawsuit/

**Duffel**
- Services Agreement (bijgewerkt 09-04-2026; fair-use, metasearch-verbod, offer-expiry): duffel.com/services-agreement
- Airline-lijst (geen Ryanair/Wizz): duffel.com/flights/airlines
- Pricing ($3/boeking, excess-search-fee 1500:1): duffel.com/pricing

**Amadeus**
- Self-Service portal ontmanteld 17-07-2026, registratie gepauzeerd (PhocusWire 09-02-2026): phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers

**RapidAPI / scrapers / officieel**
- CJEU *Ryanair v PR Aviation* (C-30/14, 15-01-2015): scraping contractueel verbiedbaar
- SerpApi door Google aangeklaagd (19-12-2025)
- Ryanair Approved OTA (Aggregators: Paxport, Travelfusion, Atlas, DerbySoft): corporate.ryanair.com
- Wizz–Kyte distributie-deal (04-12-2025): wizzair.com

### Niet (volledig) verifieerbaar — expliciet gemarkeerd
- Per-route dekking/versheid van Ryanair/Wizz vanaf jouw 5 velden bij Travelpayouts → **alleen met live token te testen** (zie checklist).
- Exacte Skyscanner affiliate-commissie % in 2026 (per partner, niet publiek).
- Exacte huidige Amadeus per-call-tarieven (prijspagina JS-rendered) — irrelevant door shutdown.
- Granulaire Kiwi Tequila-ToS (login-gated).
- Positieve EU-sanctie-clearance van Go Travel Un Limited (Travelpayouts) — niet kunnen afvinken.
- Duffel funding/klanten-cijfers 2026 (alleen secundaire bronnen).
