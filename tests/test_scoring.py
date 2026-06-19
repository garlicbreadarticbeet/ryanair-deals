"""Dealscore (puur): korting t.o.v. de mediaan, 'laagste in venster', ranking-strength."""
from __future__ import annotations

from app.core.scoring import MIN_SAMPLES, score_deal


def _baseline(median, min_total, samples=10, days_span=30):
    return {"median_total": median, "min_total": min_total, "samples": samples, "days_span": days_span}


def test_no_history_has_no_baseline():
    s = score_deal(40.0, None)
    assert s.has_baseline is False
    assert s.discount_pct == 0 and s.is_lowest is False
    # Zonder historie ranken we op goedkoopte: goedkoper → hogere strength.
    assert score_deal(30.0, None).strength > score_deal(80.0, None).strength


def test_too_few_samples_no_baseline():
    s = score_deal(40.0, _baseline(100.0, 35.0, samples=MIN_SAMPLES - 1))
    assert s.has_baseline is False
    assert s.discount_pct == 0


def test_discount_vs_median():
    s = score_deal(70.0, _baseline(100.0, 60.0))
    assert s.has_baseline is True
    assert s.discount_pct == 30
    assert s.is_notable and s.is_strong          # 30% ≥ STRONG_PCT
    assert s.is_lowest is False                   # 70 > min 60


def test_lowest_in_window_flag_and_bonus():
    low = score_deal(60.0, _baseline(100.0, 60.0))   # gelijk aan de laagste
    not_low = score_deal(61.0, _baseline(100.0, 60.0))
    assert low.is_lowest is True
    # 'laagste' krijgt een sterkte-bonus bovenop het kortingspercentage.
    assert low.strength > not_low.strength


def test_price_above_median_is_zero_discount():
    s = score_deal(120.0, _baseline(100.0, 60.0))
    assert s.discount_pct == 0 and s.is_notable is False


def test_stronger_discount_ranks_higher():
    big = score_deal(50.0, _baseline(100.0, 50.0))   # 50% korting + laagste
    small = score_deal(90.0, _baseline(100.0, 80.0))  # 10% korting
    assert big.strength > small.strength
