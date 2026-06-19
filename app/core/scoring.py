"""Dealscore — hoe goed is deze prijs t.o.v. normaal? Puur, netwerk-/DB-loos.

Krijgt de baseline-stats (mediaan/minimum/aantal waarnemingen over een venster) mee uit de
prijsgeschiedenis (repo.price_baselines) en leidt daar een leesbaar oordeel uit af: het
kortingspercentage t.o.v. de mediaan, of dit de laagste prijs in het venster is, en een
``strength`` voor het ranken (de spannendste deals bovenaan i.p.v. alleen de goedkoopste).

Geen maatschappij-/kanaal-/providernaam hier (core-purity); alleen rekenen op getallen.
"""
from __future__ import annotations

from dataclasses import dataclass

# Hoeveel waarnemingen we minstens willen voordat we over een "baseline" durven praten.
MIN_SAMPLES = 4
# Vanaf dit kortingspercentage noemen we een deal "sterk" (krijgt het vuurtje 🔥).
STRONG_PCT = 20
# Tot dit kortingspercentage tonen we geen kortingsclaim (binnen de normale ruis).
NOTABLE_PCT = 8
# Marge waarmee "gelijk aan de laagste" nog als laagste telt (centen-ruis).
_EPS = 0.01


@dataclass(frozen=True)
class DealScore:
    """Het oordeel over één prijs t.o.v. zijn historie."""

    total: float
    discount_pct: int          # % onder de mediaan (0 als geen/te weinig historie)
    is_lowest: bool            # gelijk aan of onder de laagste prijs in het venster
    samples: int               # aantal waarnemingen in het venster
    days_span: int             # over hoeveel dagen historie dat gaat
    median: float | None       # baseline-mediaan (None bij te weinig historie)
    min_recent: float | None   # laagste prijs in het venster (None bij te weinig historie)
    strength: float            # rangschik-score (hoger = spannender)

    @property
    def has_baseline(self) -> bool:
        """Genoeg historie om een betekenisvol oordeel te geven."""
        return self.median is not None and self.samples >= MIN_SAMPLES

    @property
    def is_strong(self) -> bool:
        return self.has_baseline and self.discount_pct >= STRONG_PCT

    @property
    def is_notable(self) -> bool:
        return self.has_baseline and self.discount_pct >= NOTABLE_PCT


def score_deal(total: float, baseline: dict | None) -> DealScore:
    """Beoordeel ``total`` tegen de baseline-stats (uit repo.price_baselines), of zonder historie.

    Zonder (genoeg) historie: discount 0, niet-laagste, en ``strength`` puur op goedkoopte
    (goedkoper = iets hoger), zodat de volgorde dan op prijs valt.
    """
    samples = int(baseline.get("samples", 0)) if baseline else 0
    # Expliciete None-check (geen truthiness): een legitieme baseline van 0 is geen 'ontbreekt'.
    median = float(baseline["median_total"]) if baseline and baseline.get("median_total") is not None else None
    min_recent = float(baseline["min_total"]) if baseline and baseline.get("min_total") is not None else None
    days_span = int(baseline.get("days_span", 0)) if baseline else 0

    if not baseline or samples < MIN_SAMPLES or not median or median <= 0:
        # Geen baseline → rang op goedkoopte (kleine, altijd-negatieve bijdrage).
        return DealScore(
            total=total, discount_pct=0, is_lowest=False, samples=samples,
            days_span=days_span, median=median, min_recent=min_recent,
            strength=-total / 1000.0,
        )

    discount_pct = max(0, round((median - total) / median * 100))
    is_lowest = min_recent is not None and total <= min_recent + _EPS
    # Sterkte: korting weegt het zwaarst, "laagste in N dagen" geeft een bonus, en bij
    # gelijke korting wint de goedkoopste (kleine prijs-tiebreaker).
    strength = float(discount_pct) + (8.0 if is_lowest else 0.0) - total / 10000.0
    return DealScore(
        total=total, discount_pct=discount_pct, is_lowest=is_lowest, samples=samples,
        days_span=days_span, median=median, min_recent=min_recent, strength=strength,
    )
