"""Gedeelde alert-opmaak: vlag, prijs/datumnotatie, dealscore-badge, en de e-mail/Telegram-HTML."""
from __future__ import annotations

import datetime

from app.alerts import render as R
from app.channels.base import AlertItem
from app.channels.email import _render as render_email
from app.channels.telegram import format_alerts
from app.core.combine import ReturnDeal
from app.core.scoring import score_deal

D1 = datetime.date(2026, 7, 11)   # zaterdag
D2 = datetime.date(2026, 7, 14)   # dinsdag


def _item(total=34.0, *, dest="BCN", city_to="Barcelona", cc="es", prev=None, baseline=None):
    return AlertItem(
        deal=ReturnDeal("ryanair", "EIN", dest, 3, total, D1, D2, total / 2, total / 2,
                        airline="Ryanair", deeplink="https://book.example/x"),
        previous_price=prev, city_from="Eindhoven", city_to=city_to, country_to=cc,
        score=score_deal(total, baseline),
    )


def _base(median, min_total, samples=10, days_span=42):
    return {"median_total": median, "min_total": min_total, "samples": samples, "days_span": days_span}


def test_flag_money_dates():
    assert R.flag("es") == "🇪🇸"
    assert R.flag(None) == "" and R.flag("xyz") == ""
    assert R.flag("xé") == ""              # 2 tekens maar niet-ASCII → geen vlag (geen garbage)
    assert R.money(34.0) == "€34"
    assert R.money(34.5) == "€34,50"
    assert R.money(34.99) == "€34,99"
    assert R.date_label(D1) == "za 11 jul"
    assert R.dates_label(_item()) == "za 11 jul → di 14 jul"


def test_safe_href_blocks_non_http_schemes():
    assert R.safe_href("https://book.example/x") == "https://book.example/x"
    assert R.safe_href("http://x") == "http://x"
    assert R.safe_href("javascript:alert(1)") == ""
    assert R.safe_href("data:text/html,x", "/fallback") == "/fallback"
    assert R.safe_href(None, "/fallback") == "/fallback"


def test_channels_drop_dangerous_deeplink():
    bad = AlertItem(
        deal=ReturnDeal("ryanair", "EIN", "BCN", 3, 34.0, D1, D2, 17, 17,
                        airline="Ryanair", deeplink="javascript:alert(1)"),
        city_from="Eindhoven", city_to="Barcelona", country_to="es", score=score_deal(34.0, None),
    )
    assert "javascript:" not in format_alerts([bad])
    _, body = render_email([bad])
    assert "javascript:" not in body


def test_badge_priority():
    # laagste in venster → 'hot' met "laagste in N dagen"
    low = R.badge(_item(34.0, baseline=_base(80.0, 34.0)))
    assert low.tone == "hot" and "laagste in 42 dagen" in low.text
    # sterke korting (geen laagste) → 'hot' met "% onder normaal"
    strong = R.badge(_item(50.0, baseline=_base(100.0, 40.0)))
    assert strong.tone == "hot" and "50% onder normaal" in strong.text
    # nette maar kleine korting → 'good'
    good = R.badge(_item(88.0, baseline=_base(100.0, 80.0)))
    assert good.tone == "good" and "12% onder normaal" in good.text
    # geen historie maar wel goedkoper-dan-vorige → 'info' "was €X"
    info = R.badge(_item(34.0, prev=49.0))
    assert info.tone == "info" and info.text == "was €49"
    # niets te melden
    assert R.badge(_item(34.0)) is None


def test_sort_key_ranks_strongest_first():
    weak = _item(34.0)                              # geen baseline
    strong = _item(50.0, baseline=_base(100.0, 50.0))   # 50% + laagste
    assert R.sort_key(strong) < R.sort_key(weak)   # lagere key = eerder


def test_telegram_html_has_brand_elements():
    text = format_alerts([_item(34.0, baseline=_base(80.0, 34.0))])
    assert "Barcelona" in text and "🇪🇸" in text
    assert "€34" in text and "🔥" in text
    assert "laagste in 42 dagen" in text
    assert 'href="https://book.example/x"' in text


def test_login_email_is_branded():
    from app.channels.email import _login_email
    link = "https://vliegseintje.nl/verify?token=abc123"
    subject, body = _login_email(link)
    assert "Vliegseintje" in subject
    assert "Goedkoop Vliegen" not in subject and "Goedkoop Vliegen" not in body  # oude merknaam weg
    assert "#2563EB" in body and "#FFB703" in body    # merk-blauw header + amber knop
    assert "Log in" in body and link in body           # knop + fallback-link


def test_email_html_is_branded_and_complete():
    subject, body = render_email([
        _item(34.0, baseline=_base(80.0, 34.0)),
        _item(58.0, dest="AGP", city_to="Málaga", cc="es"),
    ])
    assert "Barcelona" in subject and "€34" in subject
    assert "#2563EB" in body and "#FFB703" in body        # merk-blauw + amber
    assert "Barcelona" in body and "Málaga" in body
    assert "laagste in 42 dagen" in body
    assert "Bekijk de vlucht" in body
    assert "/preferences" in body                          # voorkeuren-link in de footer
