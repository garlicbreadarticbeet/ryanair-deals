"""Nederlandse bestemmings-labels voor de alerts: 'Stad (Vliegveld), Land'.

Ryanair vliegt vaak op secundaire luchthavens die als 'GroteStad Vliegveld' worden vermarkt
(bv. 'Barcelona Reus', 'London Stansted'). We tonen de herkenbare stad + het vliegveld tussen
haakjes + het land in het Nederlands: 'Barcelona (Reus), Spanje'. Voor niet-gecureerde
luchthavens valt het terug op de luchthavennaam uit de DB + het (vertaalde) land.

Bewust display-only data (geen logica hangt eraan); bestemmingen aanvullen = hier een regel bij.
"""
from __future__ import annotations

# IATA → Nederlands 'Stad (Vliegveld)'-label (zonder land; dat komt uit NL_COUNTRY).
# Haakjes alleen bij een secundair/anders-genoemd vliegveld; anders alleen de stad.
NL_CITY: dict[str, str] = {
    # Spanje
    "AGP": "Málaga", "ALC": "Alicante", "GRO": "Barcelona (Girona)", "IBZ": "Ibiza",
    "MAD": "Madrid", "PMI": "Palma de Mallorca", "REU": "Barcelona (Reus)", "SVQ": "Sevilla",
    "TFS": "Tenerife", "TFN": "Tenerife", "VLC": "Valencia", "BCN": "Barcelona",
    "LPA": "Gran Canaria", "ACE": "Lanzarote", "FUE": "Fuerteventura", "SCQ": "Santiago de Compostela",
    "BIO": "Bilbao", "XRY": "Jerez", "RMU": "Murcia",
    # Portugal
    "LIS": "Lissabon", "OPO": "Porto", "FAO": "Faro", "FNC": "Madeira (Funchal)", "PDL": "Azoren (Ponta Delgada)",
    # Italië
    "BGY": "Milaan (Bergamo)", "MXP": "Milaan (Malpensa)", "BLQ": "Bologna", "CTA": "Catania",
    "FCO": "Rome (Fiumicino)", "CIA": "Rome (Ciampino)", "NAP": "Napels", "PSA": "Pisa",
    "TSF": "Venetië (Treviso)", "VCE": "Venetië", "BDS": "Brindisi", "BRI": "Bari", "CAG": "Cagliari",
    "OLB": "Olbia", "TRN": "Turijn", "VRN": "Verona", "TPS": "Trapani", "AHO": "Alghero", "PMO": "Palermo",
    # Verenigd Koninkrijk + Ierland
    "STN": "Londen (Stansted)", "LTN": "Londen (Luton)", "SEN": "Londen (Southend)",
    "MAN": "Manchester", "EDI": "Edinburgh", "BHX": "Birmingham", "LPL": "Liverpool",
    "BRS": "Bristol", "NCL": "Newcastle", "LBA": "Leeds", "DUB": "Dublin", "ORK": "Cork",
    # Griekenland + Kroatië + Cyprus + Malta
    "SKG": "Thessaloniki", "ATH": "Athene", "CHQ": "Chania", "CFU": "Corfu", "RHO": "Rhodos",
    "KGS": "Kos", "JMK": "Mykonos", "JTR": "Santorini", "ZAD": "Zadar", "ZAG": "Zagreb",
    "SPU": "Split", "DBV": "Dubrovnik", "PUY": "Pula", "PFO": "Paphos", "LCA": "Larnaca", "MLA": "Malta",
    # Centraal/Oost-Europa
    "KRK": "Krakau", "WMI": "Warschau (Modlin)", "WAW": "Warschau", "WRO": "Wrocław",
    "GDN": "Gdańsk", "POZ": "Poznań", "KTW": "Katowice", "PRG": "Praag", "BUD": "Boedapest",
    "OTP": "Boekarest", "CLJ": "Cluj-Napoca", "SOF": "Sofia", "BTS": "Bratislava", "TIA": "Tirana",
    "BEG": "Belgrado", "LJU": "Ljubljana",
    # Baltische staten + Scandinavië + Finland
    "VNO": "Vilnius", "KUN": "Kaunas", "RIX": "Riga", "TLL": "Tallinn", "HEL": "Helsinki",
    "CPH": "Kopenhagen", "GOT": "Göteborg", "NYO": "Stockholm (Skavsta)", "ARN": "Stockholm",
    "OSL": "Oslo", "TRF": "Oslo (Torp)", "BLL": "Billund",
    # West-Europa (vaak secundair)
    "CRL": "Brussel (Charleroi)", "BVA": "Parijs (Beauvais)", "HHN": "Frankfurt (Hahn)",
    "FKB": "Karlsruhe/Baden-Baden", "NRN": "Weeze", "CGN": "Keulen", "BER": "Berlijn",
    "HAM": "Hamburg", "MRS": "Marseille", "NCE": "Nice", "BOD": "Bordeaux", "TLS": "Toulouse",
    # Marokko + overig
    "RAK": "Marrakech", "FEZ": "Fez", "TNG": "Tanger", "AGA": "Agadir", "NDR": "Nador",
    "VIE": "Wenen", "SXF": "Berlijn",
}

# Alpha-2 (lowercase) → Nederlands land. Dekt alle bestemmingslanden + buffer.
NL_COUNTRY: dict[str, str] = {
    "al": "Albanië", "at": "Oostenrijk", "be": "België", "bg": "Bulgarije", "ch": "Zwitserland",
    "cy": "Cyprus", "cz": "Tsjechië", "de": "Duitsland", "dk": "Denemarken", "ee": "Estland",
    "es": "Spanje", "fi": "Finland", "fr": "Frankrijk", "gb": "Verenigd Koninkrijk", "gr": "Griekenland",
    "hr": "Kroatië", "hu": "Hongarije", "ie": "Ierland", "it": "Italië", "lt": "Litouwen",
    "lv": "Letland", "ma": "Marokko", "mt": "Malta", "nl": "Nederland", "no": "Noorwegen",
    "pl": "Polen", "pt": "Portugal", "ro": "Roemenië", "rs": "Servië", "se": "Zweden",
    "si": "Slovenië", "sk": "Slowakije", "tr": "Turkije",
}


def nl_country(country_code: str | None) -> str:
    """Alpha-2 → Nederlands land (valt terug op de hoofdletter-code)."""
    if not country_code:
        return ""
    return NL_COUNTRY.get(country_code.lower(), country_code.upper())


def destination_city(iata: str, name: str | None, city: str | None) -> str:
    """'Barcelona (Reus)' — Nederlandse stad (+ vliegveld), zónder land.

    Gebruikt de gecureerde NL_CITY waar aanwezig; anders de luchthavennaam/stad uit de DB.
    """
    return NL_CITY.get(iata) or city or name or iata


def destination_label(iata: str, name: str | None, city: str | None, country_code: str | None) -> str:
    """'Barcelona (Reus), Spanje' — stad (+ vliegveld) + land in het Nederlands."""
    city_part = destination_city(iata, name, city)
    country = nl_country(country_code)
    return f"{city_part}, {country}" if country else city_part


def origin_label(iata: str, name: str | None, city: str | None) -> str:
    """Korte stadsnaam voor het vertrekveld ('Eindhoven', 'Weeze') — geen land."""
    return NL_CITY.get(iata) or city or name or iata
