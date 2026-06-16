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

    # --- Database ---
    # Lokaal/Docker default; in productie (Hetzner) via env gezet. psycopg 3-driver.
    database_url: str = "postgresql+psycopg://ryanair:ryanair@localhost:5433/ryanair"

    # --- Telegram (bestaand kanaal; namen NIET wijzigen i.v.m. CLI/Actions-compat) ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""          # CLI-eigenaar (single-user fallback bij `watch`)

    # --- E-mail (transactionele API: Resend) ---
    resend_api_key: str = ""
    resend_from: str = "deals@goedkoopvliegen.example"
    app_base_url: str = "http://localhost:8000"   # basis voor magic-links

    # --- Providers ---
    enabled_providers: str = "ryanair"  # CSV; wizzair staat als stub uit

    # --- Scan-instellingen (waren config.py) ---
    currency: str = "EUR"               # Fase 1: alles EUR
    concurrency: int = 8                # parallelle route-fetches (politeness)

    # --- Standaard-voorkeuren voor nieuwe gebruikers (waren config-globals) ---
    default_threshold: float = 50.0     # heen+terug totaal, in EUR
    default_months_ahead: int = 3
    default_trip_lengths: str = "3,5,7" # CSV van reisduren (nachten)

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
