"""SQLAlchemy 2.x-modellen — het genormaliseerde, maatschappij-agnostische datamodel.

Negen tabellen (zie Fase-A-voorstel):

  providers     — lookup van maatschappijen; anker voor de registry (enabled aan/uit)
  airports      — centrale luchthavenlijst; de ENIGE plek met IATA-codes (regel 4)
  users         — account-identiteit, minimale PII
  preferences   — 1:1 scan-voorkeuren per gebruiker (vervangt de config-globals)
  user_origins  — jointabel: de meerdere (provider, origin) per gebruiker; drijft de
                  gededupte scan-unie (schaalt met #origins, niet met #gebruikers)
  channels      — bezorgkanalen + expliciete opt-in per kanaal (GDPR)
  deals         — globale markt-state (vervangt de "units" uit state.json)
  sent_alerts   — per-gebruiker dedup (vervangt het globale state.json)
  auth_tokens   — magic-link + Telegram /start-deeplink-tokens (gehasht, met TTL)

Conventies:
- PK's = BIGINT GENERATED ... AS IDENTITY (geen extensies nodig).
- E-mail-uniqueness via een functionele index op lower(email) (geen citext-extensie).
- Prijzen = NUMERIC(8,2) (geen float-drift in de "goedkoper"-vergelijking).
- Alle gebruiker-gerelateerde tabellen hangen via ON DELETE CASCADE aan users(id),
  zodat delete_user() één DELETE is (recht op verwijdering, regel 7).
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declaratieve basis; `Base.metadata` voedt Alembic-autogenerate."""


# Hergebruikte kolomtypes / defaults
_TS = DateTime(timezone=True)
_PRICE = Numeric(8, 2)


def _now() -> Mapped[datetime.datetime]:
    return mapped_column(_TS, nullable=False, server_default=func.now())


class Provider(Base):
    """Maatschappij-lookup. Een nieuwe maatschappij = rij hier + adapter onder providers/."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # 'ryanair'
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = _now()


class Airport(Base):
    """Centrale luchthavenlijst (seed). Vertrek- en bestemmingsvelden verwijzen hierheen."""

    __tablename__ = "airports"

    iata: Mapped[str] = mapped_column(String(3), primary_key=True)               # 'EIN'
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)         # ISO alpha-2
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Markeert de oude config.ORIGINS als default-suggestie in de UI; geen logica hangt eraan.
    is_origin_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (Index("ix_airports_country", "country_code"),)


class User(Base):
    """Account-identiteit. Minimale PII; e-mail optioneel tot verificatie."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime.datetime] = _now()
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    tier: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'free'"))
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    preferences: Mapped["Preference"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    origins: Mapped[list["UserOrigin"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    channels: Mapped[list["Channel"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    sent_alerts: Mapped[list["SentAlert"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    subscription: Mapped["Subscription"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('active','paused','deleted')", name="ck_users_status"),
        CheckConstraint("tier IN ('free','premium')", name="ck_users_tier"),
        # E-mail uniek zonder citext: functionele index op lower(email), alleen waar gezet.
        Index(
            "uq_users_email_lower",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )


class Preference(Base):
    """1:1 scan-voorkeuren per gebruiker. Vervangt config.TRIP_LENGTHS/ALERT_THRESHOLD/etc.

    Reisduren en bestemmingsfilters zijn Postgres-arrays (alleen per-user gelezen in match);
    origins staan bewust in een aparte jointabel (drijven de globale scan-unie).
    """

    __tablename__ = "preferences"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    threshold: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)            # heen+terug totaal
    months_ahead: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("3"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'EUR'"))
    alert_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'instant'"))
    dest_filter_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'all'"))
    trip_lengths: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, server_default=text("'{3,5,7}'")
    )
    dest_countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)), nullable=False, server_default=text("'{}'")
    )
    dest_whitelist: Mapped[list[str]] = mapped_column(
        ARRAY(String(3)), nullable=False, server_default=text("'{}'")
    )
    dest_blacklist: Mapped[list[str]] = mapped_column(
        ARRAY(String(3)), nullable=False, server_default=text("'{}'")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        _TS, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="preferences")

    __table_args__ = (
        CheckConstraint("threshold > 0", name="ck_preferences_threshold_pos"),
        CheckConstraint("months_ahead BETWEEN 1 AND 12", name="ck_preferences_months"),
        CheckConstraint("alert_mode IN ('instant','digest')", name="ck_preferences_alert_mode"),
        CheckConstraint(
            "dest_filter_mode IN ('all','country','whitelist','blacklist')",
            name="ck_preferences_dest_mode",
        ),
    )


class UserOrigin(Base):
    """Jointabel: de gekozen (provider, origin)-vertrekvelden per gebruiker.

    Bewust geen array-kolom: de globale gededupte scan-unie is hierdoor een simpele
    SELECT DISTINCT met FK-integriteit naar airports/providers.
    """

    __tablename__ = "user_origins"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True
    )
    origin_iata: Mapped[str] = mapped_column(
        String(3), ForeignKey("airports.iata"), primary_key=True
    )

    __table_args__ = (Index("ix_user_origins_provider_origin", "provider_id", "origin_iata"),)


class Channel(Base):
    """Bezorgkanaal per gebruiker + expliciete opt-in (GDPR, regel 7)."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)                # telegram/email/whatsapp
    address: Mapped[str] = mapped_column(String(256), nullable=False)            # chat_id / e-mail / tel
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    opted_in_at: Mapped[datetime.datetime | None] = mapped_column(_TS, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        CheckConstraint("type IN ('telegram','email','whatsapp')", name="ck_channels_type"),
        UniqueConstraint("type", "address", name="uq_channels_type_address"),
        Index("ix_channels_user", "user_id"),
    )


class Deal(Base):
    """Globale markt-state: één rij per concrete retour-combinatie, gedeeld door alle gebruikers.

    Geüpsert door de scan (O(routes), niet O(gebruikers)). Vervangt de "units" uit state.json.
    """

    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    nights: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    out_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    in_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    out_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    in_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'EUR'"))
    # Retour-native bronnen (aggregators) leveren een boekingslink + maatschappij mee.
    airline: Mapped[str | None] = mapped_column(String(16), nullable=True)
    deeplink: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    found_at: Mapped[datetime.datetime] = _now()
    last_seen: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        UniqueConstraint(
            "provider", "origin", "destination", "nights", "out_date", "in_date",
            name="uq_deals_combo",
        ),
        Index("ix_deals_match", "origin", "nights", "total_price"),
    )


class SentAlert(Base):
    """Per-gebruiker dedup (vervangt het globale state.json).

    Fingerprint = (user_id, provider, origin, destination, nights, channel_type) — ZONDER
    datums, exact de relationele vertaling van de oude state-key "ORIG-DEST-Nd". alerted_price
    is de ondergrens voor "goedkoper" (epsilon 0.001), net als detect_new_deals.
    """

    __tablename__ = "sent_alerts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    nights: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    channel_type: Mapped[str] = mapped_column(String(16), nullable=False)
    alerted_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    out_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)        # informatief
    in_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)         # informatief
    last_alerted_at: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider", "origin", "destination", "nights", "channel_type",
            name="uq_sent_alerts_fingerprint",
        ),
        Index("ix_sent_alerts_user", "user_id"),
    )


class AuthToken(Base):
    """Eenmalige tokens (gehasht) voor e-mail magic-link en Telegram /start-deeplink."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # sha256 hex
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)             # email_login/telegram_link
    payload: Mapped[str | None] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(_TS, nullable=False)
    consumed_at: Mapped[datetime.datetime | None] = mapped_column(_TS, nullable=True)
    created_at: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_login','telegram_link','session')", name="ck_auth_tokens_purpose"
        ),
        Index("ix_auth_tokens_expires", "expires_at"),
    )


class ContactMessage(Base):
    """Bericht uit het publieke contactformulier (/contact). Niet aan een user gekoppeld."""

    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    handled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime.datetime] = _now()

    __table_args__ = (Index("ix_contact_messages_created", "created_at"),)


class Subscription(Base):
    """Mollie-abonnementsstatus per gebruiker (Fase 2). Eén rij per gebruiker.

    De feitelijke premium-toegang zit in users.tier; deze tabel houdt de Mollie-koppeling
    en de levenscyclus bij zodat de webhook tier kan bij- en afschalen.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    mollie_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mollie_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(_TS, nullable=True)
    created_at: Mapped[datetime.datetime] = _now()
    updated_at: Mapped[datetime.datetime] = mapped_column(
        _TS, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="subscription")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','canceled','suspended','failed')",
            name="ck_subscriptions_status",
        ),
    )
