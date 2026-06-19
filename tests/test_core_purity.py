"""Mechanische garantie voor acceptatiecriterium 1 + 5: app/core/ is provider-, kanaal- én
betaalprovider-agnostisch. Geen maatschappij-/kanaal-/betaalprovidernaam mag in core/ voorkomen,
zodat een nieuwe maatschappij/kanaal/provider echt 1 nieuw bestand onder
providers//channels//billing_providers/ is.

De verboden namen worden **dynamisch afgeleid** uit de daadwerkelijke bestanden, zodat de lijst
niet stilletjes achterloopt als er een adapter bijkomt (bv. travelpayouts).
"""
from __future__ import annotations

import pathlib

_APP = pathlib.Path(__file__).resolve().parent.parent / "app"
CORE_DIR = _APP / "core"


def _stems(subdir: str, exclude: set[str], strip_suffix: str = "") -> set[str]:
    tokens: set[str] = set()
    for py in (_APP / subdir).glob("*.py"):
        stem = py.stem
        if stem in exclude:
            continue
        if strip_suffix and stem.endswith(strip_suffix):
            stem = stem[: -len(strip_suffix)]
        tokens.add(stem.lower())
    return tokens


def _forbidden() -> set[str]:
    tokens = _stems("providers", {"__init__", "base", "registry"})
    tokens |= _stems("channels", {"__init__", "base"})
    tokens |= _stems("billing_providers", {"__init__", "base"}, strip_suffix="_provider")
    tokens |= {"whatsapp"}  # geschrapt kanaal: mag ook nooit terugkeren in core/
    return tokens


FORBIDDEN = _forbidden()


def test_forbidden_list_is_non_trivial():
    # Vangnet: als de afleiding stuk gaat, faalt de purity-test niet stil 'groen'.
    assert {"ryanair", "telegram", "email", "mollie", "lemonsqueezy", "travelpayouts"} <= FORBIDDEN


def test_core_mentions_no_carrier_or_channel():
    offences: list[str] = []
    for py in sorted(CORE_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            if token in text:
                offences.append(f"{py.name}: '{token}'")
    assert not offences, (
        "app/core/ moet maatschappij-/kanaal-/betaalprovider-agnostisch blijven, "
        "maar bevat: " + ", ".join(offences)
    )
