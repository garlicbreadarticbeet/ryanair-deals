"""Nederlandse bestemmings-labels: 'Stad (Vliegveld), Land', met fallback."""
from __future__ import annotations

from app.alerts.places import destination_city, destination_label, nl_country, origin_label


def test_destination_city_has_no_country():
    # Voor de kaart-hero: stad (+ vliegveld), zonder land.
    assert destination_city("REU", "Barcelona Reus", "Reus") == "Barcelona (Reus)"
    assert destination_city("STN", "London Stansted", "London") == "Londen (Stansted)"
    assert destination_city("VIE", "Vienna", "Vienna") == "Wenen"
    assert destination_city("XXX", None, "Someville") == "Someville"   # fallback


def test_secondary_airport_shows_city_and_airport():
    # Ryanair vermarkt deze als 'Barcelona Reus' / 'Warsaw Modlin' / 'London Stansted'.
    assert destination_label("REU", "Barcelona Reus", "Reus", "es") == "Barcelona (Reus), Spanje"
    assert destination_label("WMI", "Warsaw Modlin", "Warsaw", "pl") == "Warschau (Modlin), Polen"
    assert destination_label("STN", "London Stansted", "London", "gb") == "Londen (Stansted), Verenigd Koninkrijk"
    assert destination_label("BGY", "Milan Bergamo", "Bergamo", "it") == "Milaan (Bergamo), Italië"


def test_dutch_city_names():
    assert destination_label("VIE", "Vienna", "Vienna", "at") == "Wenen, Oostenrijk"
    assert destination_label("LIS", "Lisbon", "Lisbon", "pt") == "Lissabon, Portugal"
    assert destination_label("NAP", "Naples", "Naples", "it") == "Napels, Italië"
    assert destination_label("AGP", "Malaga", "Malaga", "es") == "Málaga, Spanje"


def test_fallback_for_uncurated_airport():
    # Onbekende IATA → luchthavennaam uit de DB + vertaald land.
    assert destination_label("XXX", "Someplace", "Someville", "fr") == "Someville, Frankrijk"
    # Onbekend land → hoofdletter-code als laatste redmiddel.
    assert destination_label("XXX", "Someplace", "Someville", "zz") == "Someville, ZZ"


def test_nl_country():
    assert nl_country("es") == "Spanje"
    assert nl_country("GB") == "Verenigd Koninkrijk"
    assert nl_country("") == "" and nl_country(None) == ""


def test_origin_label_has_no_country():
    assert origin_label("EIN", "Eindhoven", "Eindhoven") == "Eindhoven"
    assert origin_label("NRN", "Weeze", "Weeze") == "Weeze"
