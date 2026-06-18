# ============================================================
# Horse Racing Research Agent — Configuration
# ============================================================

import os

# --- Tracks to monitor ---
# Priority tracks fetched first — Grade 1 and major tracks
PRIORITY_TRACKS = [
    "Keeneland", "Churchill Downs", "Belmont Park", "Aqueduct",
    "Saratoga", "Gulfstream Park", "Santa Anita", "Del Mar",
    "Oaklawn Park", "Fair Grounds", "Pimlico", "Laurel Park",
    "Tampa Bay", "Parx Racing", "Monmouth Park", "Sam Houston",
    "Sunland Park", "Turf Paradise", "Charles Town",
]

# Tracks to permanently exclude (even if Equibase shows them as active)
EXCLUDED_TRACKS = [
    "Camarero",
    "Old Dominion Hounds",  # Hunt meet, not standard thoroughbred
    "Club Hipico Concepcion Chile",
    "Gavea Brazil",
    "Presidente Remon Panama",
    "Weber Downs",  # WBR - Equibase mobile chart has no payout data
    "Delta Downs",  # DED - races too short, mixed thoroughbred/QH card
    "Miles City",   # MC  - not available on NYRA Bets
    "Lone Star",    # LS  - not available on NYRA Bets
    "Century Mile",          # CTM - Canadian QH track, not on NYRA Bets
    "Ajax Downs",            # AJX - Canadian QH track, not on NYRA Bets
    "Assiniboia",            # ASD - Canadian track, not on NYRA Bets
    "Lethbridge - Rmtc",     # LBG - Canadian track, not on NYRA Bets
    "Los Alamitos Quarter Horse", # LA - QH races, not on NYRA Bets
    "Malvern",               # MAL - UK/International, not on NYRA Bets
    "Percy Warner",          # PW  - Steeplechase/hunt meet
    "Pocatello Downs",       # POD - Idaho, not on NYRA Bets
    "Sunray Park",           # SRP - New Mexico small track, not on NYRA Bets
    "Willowdale Stp",        # WIL - Steeplechase, not on NYRA Bets
    "Legacy Downs",          # LEG - Not on NYRA Bets
    "Bes Preakness Double",  # EQM - Exotic wager, not a real track
    "Remington Park",       # RP  - Short races, not worth tracking
]

# Set to True to only fetch priority tracks (faster)
# Set to False to fetch all tracks (slower but complete)
PRIORITY_ONLY = False

# All active US Thoroughbred tracks
TRACKS = [
    {"name": "Churchill Downs",     "code": "CD",  "state": "KY"},
    {"name": "Keeneland",           "code": "KEE", "state": "KY"},
    {"name": "Turfway Park",        "code": "TP",  "state": "KY"},
    {"name": "Belmont Park",        "code": "BEL", "state": "NY"},
    {"name": "Aqueduct",            "code": "AQU", "state": "NY"},
    {"name": "Saratoga",            "code": "SAR", "state": "NY"},
    {"name": "Gulfstream Park",     "code": "GP",  "state": "FL"},
    {"name": "Tampa Bay Downs",     "code": "TAM", "state": "FL"},
    {"name": "Pimlico",             "code": "PIM", "state": "MD"},
    {"name": "Laurel Park",         "code": "LRL", "state": "MD"},
    {"name": "Santa Anita",         "code": "SA",  "state": "CA"},
    {"name": "Del Mar",             "code": "DMR", "state": "CA"},
    {"name": "Golden Gate Fields",  "code": "GG",  "state": "CA"},
    {"name": "Los Alamitos",        "code": "LRC", "state": "CA"},
    {"name": "Oaklawn Park",        "code": "OP",  "state": "AR"},
    {"name": "Fair Grounds",        "code": "FG",  "state": "LA"},
    {"name": "Delta Downs",         "code": "DED", "state": "LA"},
    {"name": "Evangeline Downs",    "code": "EVD", "state": "LA"},
    {"name": "Monmouth Park",       "code": "MTH", "state": "NJ"},
    {"name": "Parx Racing",         "code": "PRX", "state": "PA"},
    {"name": "Penn National",       "code": "PEN", "state": "PA"},
    {"name": "Mountaineer Park",    "code": "MNR", "state": "WV"},
    {"name": "Charles Town",        "code": "CT",  "state": "WV"},
    {"name": "Horseshoe Indianapolis", "code": "IND", "state": "IN"},
    {"name": "Indiana Grand",       "code": "IND", "state": "IN"},
    {"name": "Prairie Meadows",     "code": "PRM", "state": "IA"},
    {"name": "Canterbury Park",     "code": "CBY", "state": "MN"},
    {"name": "Remington Park",      "code": "RP",  "state": "OK"},
    {"name": "Will Rogers Downs",   "code": "WRD", "state": "OK"},
    {"name": "Lone Star Park",      "code": "LS",  "state": "TX"},
    {"name": "Sam Houston Race Park","code": "HOU", "state": "TX"},
    {"name": "Retama Park",         "code": "RET", "state": "TX"},
    {"name": "Emerald Downs",       "code": "EMD", "state": "WA"},
    {"name": "Portland Meadows",    "code": "PM",  "state": "OR"},
    {"name": "Fonner Park",         "code": "FON", "state": "NE"},
    {"name": "Sunland Park",        "code": "SUN", "state": "NM"},
    {"name": "Ruidoso Downs",       "code": "RUI", "state": "NM"},
    {"name": "Arizona Downs",       "code": "TUP", "state": "AZ"},
]

# --- Scraping settings ---
SCRAPE_INTERVAL_MIN  = 10       # How often to check scratches/results/picks (minutes)
LOOP_INTERVAL_MIN    = 5        # Main loop sleep interval (minutes)
ODDS_INTERVAL_MIN    = LOOP_INTERVAL_MIN  # alias — live odds not implemented yet
SCRATCH_CHECK_HOUR_ET = 10      # Skip scratch detection before this hour (ET)
REQUEST_TIMEOUT      = 15       # HTTP request timeout (seconds)
REQUEST_DELAY        = 0.5      # Delay between requests (seconds) — be polite

# Canadian tracks use mobile scratch feed instead of desktop
CANADIAN_TRACKS = {"WO", "WOT", "WOD", "HST", "GLD"}

# --- Dashboard URL (override via RACING_DASHBOARD_URL env var) ---
DASHBOARD_PUBLIC_URL = os.environ.get(
    "RACING_DASHBOARD_URL", "http://100.68.82.83:8081/racing.html"
)

# --- Handicapping weights ---
SPEED_FIGURE_WEIGHT  = 0.35     # 35% weight on speed figures
JOCKEY_WEIGHT        = 0.20     # 20% weight on jockey win %
TRAINER_WEIGHT       = 0.20     # 20% weight on trainer win %
CLASS_WEIGHT         = 0.15     # 15% weight on class level
PACE_WEIGHT          = 0.10     # 10% weight on pace scenario

# --- Paths ---
DB_PATH              = "db/racing.db"
LOG_PATH             = "logs/racing.log"
DASHBOARD_OUTPUT     = "dashboard/racing.html"

# --- Dashboard server ---
DASHBOARD_PORT       = 8081     # Different port from trading agent (8080)
