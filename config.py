"""Configuratie voor de Ryanair retour-deal-scanner. Pas hier alles aan."""
from pathlib import Path

# Vertrekvelden (IATA-codes)
ORIGINS = ["AMS", "EIN", "NRN", "MST", "GRQ"]
#   AMS = Amsterdam Schiphol     EIN = Eindhoven        NRN = Weeze (Niederrhein)
#   MST = Maastricht Aachen      GRQ = Groningen Eelde
# NB: Ryanair vliegt nauwelijks/niet vanaf AMS/MST/GRQ; EIN en NRN hebben het aanbod.

CURRENCY = "EUR"

# Hoe ver vooruit zoeken (vertrekdatum heenreis)
MONTHS_AHEAD = 3

# Reisduren (in dagen) die als aparte kolommen getoond worden
TRIP_LENGTHS = [3, 5, 7]

# Alert-drempel: meld een retour (heen+terug TOTAAL) met een prijs <= dit bedrag
ALERT_THRESHOLD = 50.0

# Hoeveel routes tegelijk ophalen (per-dag prijzen). 8 is rustig; verlaag bij fouten.
CONCURRENCY = 8

# Optionele filters (None / lege set = uit)
DESTINATION_COUNTRY = None        # bijv. "es" voor alleen Spanje, "it" voor Italie
ONLY_DESTINATIONS = None          # bijv. {"BCN", "FAO"} om alleen die te tonen
EXCLUDE_DESTINATIONS = set()      # bijv. {"STN"} om Londen Stansted te negeren

# Mappen / bestanden (niet aanpassen nodig)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
REPORT_MD = DATA_DIR / "report.md"
REPORT_CSV = DATA_DIR / "report.csv"
