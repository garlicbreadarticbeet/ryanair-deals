"""Gedeelde domeinfouten."""
from __future__ import annotations


class PremiumRequired(Exception):
    """Een gratis account probeert iets wat premium vereist (bv. te veel vertrekvelden)."""
