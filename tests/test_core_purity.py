"""Mechanische garantie voor acceptatiecriterium 1 + 5: app/core/ is provider- én
kanaal-agnostisch. Geen enkele maatschappij- of kanaalnaam mag in core/ voorkomen,
zodat een nieuwe maatschappij/kanaal echt 1 nieuw bestand onder providers//channels/ is.
"""
from __future__ import annotations

import pathlib

FORBIDDEN = ("ryanair", "wizzair", "telegram", "whatsapp", "mollie", "lemonsqueezy")
CORE_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "core"


def test_core_mentions_no_carrier_or_channel():
    offences: list[str] = []
    for py in sorted(CORE_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            if token in text:
                offences.append(f"{py.name}: '{token}'")
    assert not offences, (
        "app/core/ moet maatschappij-/kanaal-agnostisch blijven, maar bevat: " + ", ".join(offences)
    )
