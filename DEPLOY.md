# Deploy — Vliegseintje op een Hetzner-VPS

De hele stack draait in Docker op één Linux-VPS: **db + migrate + worker + bot + web + caddy**
(reverse proxy met automatische HTTPS). Geschat: CX22 (2 vCPU / 4 GB) volstaat om te starten;
CX32 (8 GB) geeft lucht voor de scan-worker.

## 1. VPS + DNS
1. Maak een **Hetzner Cloud**-server (Ubuntu 24.04, CX22/CX32). Noteer het IPv4-adres.
2. Zet bij je domeinprovider een **A-record**: `vliegseintje.nl` → `VPS-IP`
   (optioneel ook `www.vliegseintje.nl` → VPS-IP; zie `deploy/Caddyfile`).
3. Open in de Hetzner-firewall alleen **22 (SSH)**, **80** en **443**.
   8000 en 5433 hoeven niet open te staan (Caddy is de enige publieke ingang).

## 2. Server klaarmaken
```bash
ssh root@VPS-IP
curl -fsSL https://get.docker.com | sh          # Docker + compose-plugin
git clone <repo-url> vliegseintje && cd vliegseintje
cp .env.example .env
```

## 3. Secrets invullen (`.env`)
Vul minimaal in:
- `SITE_DOMAIN=vliegseintje.nl` en `APP_BASE_URL=https://vliegseintje.nl`
- `DATABASE_URL` mag de compose-default blijven (interne `db`-host); kies wel een sterk
  `POSTGRES_PASSWORD` in `docker-compose.yml` als dit publiek draait.
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_BOT_USERNAME` (bot + koppel-deeplink)
- `RESEND_API_KEY` + `RESEND_FROM` (geverifieerd afzenddomein) — anders gaan magic-links/digests niet uit
- `MOLLIE_API_KEY` + `PREMIUM_PRICE` (zonder prijs is checkout uit)
- `TRAVELPAYOUTS_TOKEN` + `TRAVELPAYOUTS_MARKER` (databron + affiliate; zie DECISIONS D8)

## 4. Starten
```bash
docker compose --profile prod up -d --build
```
Dit start: `db` → `migrate` (alembic + airport/provider-seed, eenmalig) → `worker`, `bot`, `web`
en `caddy`. Caddy haalt automatisch een Let's Encrypt-certificaat voor `SITE_DOMAIN`
(DNS moet wijzen + 80/443 open).

## 5. Controleren
```bash
curl https://vliegseintje.nl/health        # {"status":"ok"}
docker compose logs -f caddy               # TLS-provisioning
docker compose logs -f worker bot          # scan + bot
```
Open `https://vliegseintje.nl` in de browser.

## Beheer
- **Bijwerken:** `git pull && docker compose --profile prod up -d --build`
  (`migrate` draait opnieuw en is idempotent).
- **Logs:** `docker compose logs -f <service>`.
- **Stoppen:** `docker compose --profile prod down` (data blijft in het `gv_pgdata`-volume).
- **DB-backup:** `docker compose exec db pg_dump -U ryanair ryanair > backup.sql`.

## Hardening (aanrader vóór echte gebruikers)
- Zet een sterk `POSTGRES_PASSWORD` (niet de `ryanair/ryanair`-default) en pas `DATABASE_URL` aan.
- Draai niet als root: maak een sudo-gebruiker + SSH-keys, schakel wachtwoord-login uit.
- Overweeg de session-cookie als `Secure` te markeren (alleen-HTTPS) — kleine app-aanpassing.
- Lokale CLI-noot: de `.venv`-console-scripts hebben een verouderde shebang; gebruik
  `python -m alembic` / `python -m uvicorn` (in Docker speelt dit niet — daar is de image vers).
