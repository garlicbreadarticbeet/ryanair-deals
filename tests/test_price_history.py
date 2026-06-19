"""Prijsgeschiedenis: dagelijkse waarneming (laagste per dag) + baseline-aggregatie."""
from __future__ import annotations

import datetime

from app.db import repo

D0 = datetime.date(2026, 6, 1)
FP = ("ryanair", "EIN", "BCN", 3)


def _record(db, total, on, fp=FP):
    repo.record_price_point(
        db, provider=fp[0], origin=fp[1], destination=fp[2], nights=fp[3],
        total_price=total, observed_on=on,
    )
    db.flush()


def test_keeps_lowest_price_per_day(db):
    _record(db, 60.0, D0)
    _record(db, 45.0, D0)   # zelfde dag, goedkoper → wint
    _record(db, 70.0, D0)   # zelfde dag, duurder → genegeerd
    # Query met today = dag erna, zodat D0 als 'eerdere' dag meetelt (vandaag is uitgesloten).
    base = repo.price_baselines(db, {FP}, today=D0 + datetime.timedelta(days=1), window_days=30)
    assert base[FP]["samples"] == 1
    assert base[FP]["min_total"] == 45.0


def test_baseline_median_min_and_span(db):
    for i, price in enumerate([100.0, 80.0, 60.0, 40.0, 50.0]):
        _record(db, price, D0 + datetime.timedelta(days=i))   # D0..D0+4
    today = D0 + datetime.timedelta(days=5)                    # alle 5 dagen zijn 'eerder'
    base = repo.price_baselines(db, {FP}, today=today, window_days=90)[FP]
    assert base["samples"] == 5
    assert base["min_total"] == 40.0
    assert base["median_total"] == 60.0          # mediaan van [40,50,60,80,100]
    assert base["days_span"] == 5                # D0 → D0+5 = 5 dagen historie


def test_today_is_excluded_from_baseline(db):
    # Alleen een waarneming van 'vandaag' → geen eerdere historie → geen baseline.
    _record(db, 30.0, D0)
    assert repo.price_baselines(db, {FP}, today=D0, window_days=30) == {}


def test_window_excludes_old_points(db):
    _record(db, 30.0, D0)                                  # buiten venster
    _record(db, 90.0, D0 + datetime.timedelta(days=40))   # binnen venster
    today = D0 + datetime.timedelta(days=41)              # D0+40 telt als 'eerder'
    base = repo.price_baselines(db, {FP}, today=today, window_days=10)[FP]
    assert base["samples"] == 1 and base["min_total"] == 90.0


def test_unknown_route_absent(db):
    _record(db, 50.0, D0)
    base = repo.price_baselines(
        db, {("ryanair", "EIN", "AGP", 5)}, today=D0 + datetime.timedelta(days=1), window_days=30
    )
    assert base == {}
