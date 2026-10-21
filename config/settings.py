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
    "Harrah's Columbus Nebraska",  # Not on NYRA Bets
    "Eureka",                # EUR - mixed Paint/QH/TB card; Equibase posts entries but no results or charts
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
ODDS_INTERVAL_MIN    = LOOP_INTERVAL_MIN  # live odds fetched each data cycle
SCRATCH_CHECK_HOUR_ET = 10      # Skip scratch detection before this hour (ET)
REQUEST_TIMEOUT      = 15       # HTTP request timeout (seconds)
REQUEST_DELAY        = 0.5      # Delay between requests (seconds) — be polite

# Canadian tracks use mobile scratch feed instead of desktop, and Equibase's
# "CAN" country suffix for late-changes pages and chart PDFs
CANADIAN_TRACKS = {"WO", "WOT", "WOD", "HST", "GLD", "CTD", "FE", "GPR"}

# --- Dashboard URL (override via RACING_DASHBOARD_URL env var) ---
DASHBOARD_PUBLIC_URL = os.environ.get(
    "RACING_DASHBOARD_URL", "https://collaborease.com/racing/racing.html"
)

# --- S3 publish after each dashboard regen (Mac Mini → collaborease.com) ---
# Set RACING_DASHBOARD_S3=0 to disable. Override destination with RACING_DASHBOARD_S3_URI.
DASHBOARD_S3_ENABLED = os.environ.get("RACING_DASHBOARD_S3", "1").strip().lower() not in (
    "0", "false", "no", "off",
)
DASHBOARD_S3_URI = os.environ.get(
    "RACING_DASHBOARD_S3_URI", "s3://collaborease.com/racing/racing.html"
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

# Exacta base wager each track's payouts are quoted at (results store payouts
# as Equibase posts them). Derived from data/charts PDFs, 2026-10-16. Tracks
# not listed fall back to EXACTA_BASE_DEFAULT ($2 = conservative: never
# overstates returns).
EXACTA_BASE_1 = {
    "ALB", "AQU", "BAQ", "BEL", "BTP", "CBY", "CNL", "CT", "DED", "DEL", "DMR", "EMD",
    "EVD", "FAI", "FAR", "FP", "GP", "GRP", "HAW", "HOU", "KD", "KEE", "LA", "LAD",
    "LRC", "LRL", "MED", "MTH", "OP", "PEN", "SA", "SAR", "SRP", "SWF", "TAM", "TDN",
    "TIM", "TUP", "WO", "FE", "WYO",
}
EXACTA_BASE_2 = {
    "ARP", "ATO", "BKF", "CAS", "CD", "CPW", "EDR", "ELK", "ELP", "FL", "FMT", "FON",
    "GIL", "HPO", "IND", "JRM", "LEG", "LS", "MC", "ONE", "PID", "POD", "PRM", "PRX",
    "RET", "RP", "SRR", "WRD", "CTD",
}
EXACTA_BASE_DEFAULT = 2.0


def exacta_base(track_code: str) -> float:
    if track_code in EXACTA_BASE_1:
        return 1.0
    if track_code in EXACTA_BASE_2:
        return 2.0
    return EXACTA_BASE_DEFAULT

# Trifecta base wager per track (payouts are quoted at it). Same source as
# above; unlisted tracks fall back to $2 (conservative).
TRIFECTA_BASE = {
    "ALB": 0.5, "AQU": 0.5, "ARP": 2, "ATO": 0.5, "BAQ": 0.5, "BEL": 0.5, "BKF": 2,
    "BTP": 0.5, "CAS": 2, "CBY": 0.5, "CD": 0.5, "CNL": 0.5, "CPW": 2, "CT": 1,
    "DED": 0.5, "DEL": 0.5, "DMR": 0.5, "EDR": 1, "ELK": 2, "ELP": 0.5, "EMD": 0.5,
    "EVD": 0.5, "FAI": 1, "FAR": 0.5, "FL": 0.5, "FMT": 0.5, "FON": 0.5, "FP": 1,
    "GIL": 2, "GP": 0.5, "GRP": 1, "HAW": 0.5, "HOU": 0.5, "IND": 0.5, "JRM": 2,
    "KD": 0.5, "KEE": 0.5, "LA": 1, "LAD": 0.5, "LEG": 0.5, "LRC": 1, "LRL": 1,
    "LS": 0.5, "MC": 2, "MED": 0.5, "MNR": 1, "MTH": 0.5, "ONE": 2, "OP": 0.5,
    "PEN": 0.5, "PID": 2, "POD": 2, "PRM": 0.5, "PRV": 2, "PRX": 0.5, "RET": 0.5,
    "RP": 0.5, "SA": 1, "SAR": 0.5, "SRP": 0.5, "SRR": 0.5, "SWF": 0.5, "TAM": 0.5,
    "TDN": 0.5, "TIL": 2, "TIM": 1, "TUP": 0.5, "UN": 2, "WRD": 0.5, "WYO": 0.5,
    # Canadian charts (2026-10): WO/FE $0.20 Trifecta/Triactor, CTD $0.50
    "WO": 0.2, "FE": 0.2, "CTD": 0.5,
}
TRIFECTA_BASE_DEFAULT = 2.0


def trifecta_base(track_code: str) -> float:
    return TRIFECTA_BASE.get(track_code, TRIFECTA_BASE_DEFAULT)


# Daily double base wager per track, read from chart PDFs (2026-10). Payouts in
# results.daily_double_payout are stored at this base.
DAILY_DOUBLE_BASE = {
    "ALB": 1, "ATO": 2, "BEL": 1, "BKF": 2, "BTP": 1, "CBY": 2, "CD": 1, "CNL": 1,
    "CT": 2, "CTD": 2, "DEL": 1, "DMR": 2, "ELK": 2, "EMD": 1, "EVD": 1, "FE": 1,
    "FH": 1, "FL": 2, "FP": 1, "GP": 1, "GRP": 2, "IND": 2, "KD": 1, "KEE": 1,
    "LAD": 1, "LRC": 2, "LRL": 1, "MED": 1, "MNR": 2, "MTH": 1, "MVR": 2, "PEN": 1,
    "PID": 2, "PRM": 2, "PRX": 2, "SA": 2, "SAR": 1, "SRR": 2, "SWF": 2, "TDN": 1,
    "TIM": 1, "WO": 1, "WRD": 2,
}
DAILY_DOUBLE_BASE_DEFAULT = 2.0


def daily_double_base(track_code: str) -> float:
    return float(DAILY_DOUBLE_BASE.get(track_code, DAILY_DOUBLE_BASE_DEFAULT))


# Rolling double (top 3 x top 3 picks, 9 combos) play list. Chosen from
# 9/1-10/19 backtest: GP +42%, LRL +27%, WO +6% over 96-162 doubles each; SA
# -15% but 45% hits and the new model hits 67% there. FL added 2026-10-21:
# -8.6% since 9/1 but +13.5% over the last 30 days (79 doubles). Revisit monthly.
ROLLING_DOUBLE_TRACKS = ["GP", "LRL", "WO", "SA", "FL"]

# Stake per combo actually bet, where it differs from the chart base. A $1
# combo at a $2-base track returns half the posted payout.
ROLLING_DOUBLE_STAKE = {"FL": 1}


def rolling_double_stake(track_code: str) -> float:
    return float(ROLLING_DOUBLE_STAKE.get(track_code, daily_double_base(track_code)))

# Equibase post times are track-local with no AM/PM. Tracks not listed are
# US Eastern. Used to convert post times to ET for the pick freeze/lock.
TRACK_TIMEZONES = {
    # Central
    "CBY": "America/Chicago", "DED": "America/Chicago", "ELP": "America/Chicago",
    "EVD": "America/Chicago", "FAR": "America/Chicago", "FMT": "America/Chicago",
    "FON": "America/Chicago", "FP": "America/Chicago", "FTP": "America/Chicago",
    "GIL": "America/Chicago", "HAW": "America/Chicago", "HOU": "America/Chicago",
    "HPO": "America/Chicago", "ATO": "America/Chicago", "CPW": "America/Chicago",
    "KD": "America/Chicago", "LAD": "America/Chicago", "LS": "America/Chicago",
    "OP": "America/Chicago", "PRM": "America/Chicago", "RET": "America/Chicago",
    "RP": "America/Chicago", "WRD": "America/Chicago",
    # Mountain
    "ALB": "America/Denver", "ARP": "America/Denver", "BKF": "America/Boise",
    "CAS": "America/Boise", "CTD": "America/Edmonton", "EDR": "America/Denver",
    "GPR": "America/Edmonton", "JRM": "America/Boise", "MC": "America/Denver",
    "MIL": "America/Edmonton", "ONE": "America/Boise", "POD": "America/Boise",
    "SRP": "America/Denver", "SWF": "America/Denver", "WYO": "America/Denver",
    "TUP": "America/Phoenix",
    # Pacific
    "DMR": "America/Los_Angeles", "ELK": "America/Los_Angeles",
    "ELY": "America/Los_Angeles", "EMD": "America/Los_Angeles",
    "GRP": "America/Los_Angeles", "LA": "America/Los_Angeles",
    "LRC": "America/Los_Angeles", "PRV": "America/Los_Angeles",
    "SA": "America/Los_Angeles", "TIL": "America/Los_Angeles",
    "UN": "America/Los_Angeles",
}
DEFAULT_TRACK_TIMEZONE = "America/New_York"
