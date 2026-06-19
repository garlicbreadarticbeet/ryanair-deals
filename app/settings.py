"""Centrale configuratie via omgevingsvariabelen (pydantic-settings).

Vervangt het losse `notify._load_env()` en de globals in `config.py`. Leest `.env`
lokaal (nooit in git) en valt anders terug op de defaults hieronder. De oude
Telegram-env-namen blijven identiek zodat de bestaande CLI (`deals.py scan/watch`)
en de GitHub Actions-secrets ongewijzigd blijven werken.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Alle instellingen; per veld te overschrijven met een gelijknamige env-var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Merk (UI; centraal zodat naam/tagline op één plek te wijzigen zijn) ---
    brand_name: str = "Vliegseintje"
    brand_tagline: str = "Goedkoop vliegen, zonder zoeken."
    # Social handles (zonder @) — alleen getoond als gezet. Inschattingen uit het merkdoc.
    social_instagram: str = "vliegseintje"
    social_tiktok: str = "vliegseintje"
    social_x: str = "vliegseintje"
    support_email: str = ""             # ontvanger contactformulier; valt terug op resend_from

    # --- Privacyvriendelijke analytics + foutmonitoring (opt-in via env) ---
    plausible_domain: str = ""          # bv. "vliegseintje.nl"; script alleen geladen als gezet
    sentry_dsn: str = ""

    # --- Database ---
    # Lokaal/Docker default; in productie (Hetzner) via env gezet. psycopg 3-driver.
    database_url: str = "postgresql+psycopg://ryanair:ryanair@localhost:5433/ryanair"

    # --- Telegram (bestaand kanaal; namen NIET wijzigen i.v.m. CLI/Actions-compat) ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""          # CLI-eigenaar (single-user fallback bij `watch`)
    telegram_bot_username: str = ""     # voor de /start-deeplink op de website (zonder @)

    # --- E-mail (transactionele API: Resend) ---
    resend_api_key: str = ""
    resend_from: str = "deals@goedkoopvliegen.example"
    app_base_url: str = "http://localhost:8000"   # basis voor magic-links

    # --- Providers ---
    enabled_providers: str = "ryanair"  # CSV; wizzair staat als stub uit

    # --- Travelpayouts (databron + affiliate; cached Data API — zie DECISIONS D8) ---
    travelpayouts_token: str = ""        # API-token uit je Travelpayouts-account (Data API)
    travelpayouts_marker: str = ""       # affiliate-marker (Partner ID) voor de deeplinks
    travelpayouts_market: str = "nl"     # markt/locale voor de prijs-cache (nl/be)

    # --- Scan-instellingen (waren config.py) ---
    currency: str = "EUR"               # Fase 1: alles EUR
    concurrency: int = 8                # parallelle route-fetches (politeness)

    # --- Standaard-voorkeuren voor nieuwe gebruikers (waren config-globals) ---
    default_threshold: float = 50.0     # heen+terug totaal, in EUR
    default_months_ahead: int = 3
    default_trip_lengths: str = "3,5,7" # CSV van reisduren (nachten)

    # --- Premium / gating (Fase 2) ---
    # Features die alleen premium mag (CSV). Hier staan de kanaal-/modusnamen, NIET in core/.
    premium_only_features: str = "mode:instant,channel:whatsapp"
    free_max_origins: int = 1           # max vertrekvelden voor een gratis account

    # --- Mollie-abonnement (Fase 2) ---
    mollie_api_key: str = ""            # test_... of live_...
    premium_price: str = ""             # bv. "2.99" — verplicht in te vullen vóór checkout
    premium_currency: str = "EUR"
    premium_interval: str = "1 month"   # Mollie-intervalformaat
    premium_description: str = "Goedkoop Vliegen Premium"

    # --- WhatsApp (Fase 2; uit tot credentials aanwezig zijn) ---
    whatsapp_enabled: bool = False
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""

    @property
    def premium_only_feature_set(self) -> set[str]:
        """Premium-only features als set (uit de CSV-env)."""
        return {f.strip() for f in self.premium_only_features.split(",") if f.strip()}

    @property
    def enabled_provider_list(self) -> list[str]:
        """Actieve providercodes als lijst (uit de CSV-env)."""
        return [p.strip().lower() for p in self.enabled_providers.split(",") if p.strip()]

    @property
    def default_trip_length_list(self) -> list[int]:
        """Standaard-reisduren als lijst van ints (uit de CSV-env)."""
        return [int(n) for n in self.default_trip_lengths.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    """Gecachte settings-instantie (één keer ingelezen per proces)."""
    return Settings()


# Gemaksimport: `from app.settings import settings`
settings = get_settings()
