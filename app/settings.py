"""Centrale configuratie via omgevingsvariabelen (pydantic-settings).

Vervangt het losse `notify._load_env()` en de globals in `config.py`. Leest `.env`
lokaal (nooit in git) en valt anders terug op de defaults hieronder. De oude
Telegram-env-namen blijven identiek zodat de bestaande CLI (`deals.py scan/watch`)
en de GitHub Actions-secrets ongewijzigd blijven werken.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _eur(value: Decimal) -> str:
    """Decimal → NL-bedrag met twee decimalen en komma: 2.08 → '2,08'."""
    q = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:.2f}".replace(".", ",")


@dataclass(frozen=True)
class PremiumPricing:
    """Afgeleide prijs-/besparingsweergave voor de templates (uit de config berekend).

    Zo hoeven de templates zelf niets te rekenen en klopt de korting automatisch als de
    prijs ooit wijzigt. ``monthly``/``annual`` zijn de rauwe bedragen voor de betaal-API
    (punt-decimaal); de ``*_display``-velden zijn de NL-weergave (komma).
    """

    currency: str
    monthly: str                    # rauw, bv. "2.99" (voor de provider-API)
    annual: str                     # rauw, bv. "24.99"
    monthly_display: str            # "2,99"
    annual_display: str             # "24,99"
    annual_per_month_display: str   # "2,08" — jaarplan omgerekend naar per maand
    saving_pct: int                 # 30 — hoeveel goedkoper jaar dan 12× maand
    months_free: int                # 3 — "ruim N maanden gratis"


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
    # Databron waaraan nieuwe vertrekvelden worden gekoppeld (drijft welke adapter de scan
    # voor die origins gebruikt). 'travelpayouts' = de gecachte Data API (zie DECISIONS D8);
    # 'ryanair' = de legacy directe cheapestPerDay-bron.
    default_origin_provider: str = "travelpayouts"

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
    premium_only_features: str = "mode:instant"
    free_max_origins: int = 1           # max vertrekvelden voor een gratis account

    # --- Prijzen (maand + jaar; incl. btw, in EUR). Komen volledig uit config. ---
    premium_price_monthly: str = "2.99"   # € per maand
    premium_price_annual: str = "24.99"   # € per jaar (≈ €2,08/maand, ~30% goedkoper)
    premium_currency: str = "EUR"
    premium_description: str = "Vliegseintje Premium"

    # --- Betaalprovider-keuze: "lemonsqueezy" (Merchant of Record, geen KvK nodig) of "mollie" ---
    billing_provider: str = "lemonsqueezy"

    # --- Lemon Squeezy (Merchant of Record; regelt EU-btw). Uit tot credentials gezet. ---
    lemonsqueezy_api_key: str = ""
    lemonsqueezy_store_id: str = ""
    lemonsqueezy_variant_monthly: str = ""    # variant-ID van het maandplan
    lemonsqueezy_variant_annual: str = ""     # variant-ID van het jaarplan
    lemonsqueezy_webhook_secret: str = ""     # HMAC-secret voor X-Signature

    # --- Mollie-abonnement (latere optie na KvK; interval per plan, Mollie-formaat) ---
    mollie_api_key: str = ""               # test_... of live_...
    mollie_interval_monthly: str = "1 month"
    mollie_interval_annual: str = "12 months"

    @property
    def premium_pricing(self) -> PremiumPricing:
        """Maand-/jaarprijs + besparing, berekend uit de config (voor de view-context)."""
        monthly = Decimal(self.premium_price_monthly or "0")
        annual = Decimal(self.premium_price_annual or "0")
        yearly_if_monthly = monthly * 12
        saving_pct = months_free = 0
        if yearly_if_monthly > 0:
            saving = yearly_if_monthly - annual
            saving_pct = int((saving / yearly_if_monthly * 100).to_integral_value(ROUND_HALF_UP))
            if monthly > 0:
                months_free = int((saving / monthly).to_integral_value(ROUND_FLOOR))
        per_month = annual / 12 if annual > 0 else Decimal("0")
        return PremiumPricing(
            currency=self.premium_currency,
            monthly=self.premium_price_monthly,
            annual=self.premium_price_annual,
            monthly_display=_eur(monthly),
            annual_display=_eur(annual),
            annual_per_month_display=_eur(per_month),
            saving_pct=saving_pct,
            months_free=months_free,
        )

    def premium_price_for(self, plan: str) -> str:
        """Rauw prijsbedrag voor het gekozen plan ('monthly'/'annual')."""
        return self.premium_price_annual if plan == "annual" else self.premium_price_monthly

    def mollie_interval_for(self, plan: str) -> str:
        """Mollie-intervalstring voor het gekozen plan."""
        return self.mollie_interval_annual if plan == "annual" else self.mollie_interval_monthly

    def lemonsqueezy_variant_for(self, plan: str) -> str:
        """Lemon Squeezy variant-ID voor het gekozen plan."""
        return self.lemonsqueezy_variant_annual if plan == "annual" else self.lemonsqueezy_variant_monthly

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
