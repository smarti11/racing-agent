# ============================================================
# Meet leaders and track-specific jockey boost configuration
# ============================================================
# To update for a new meet: edit MEET_LEADERS[track_code] with the
# current leading jockeys' name variants (all lowercase). Remove or
# replace old entries when a meet ends or leadership changes.

ORTIZ_CD_TRACK      = "CD"
ORTIZ_CD_MULTIPLIER = 1.30

MEET_LEADER_MULTIPLIER = 1.20

# Irad Ortiz Jr. — all known name variants (lowercase)
_IRAD_VARIANTS = [
    "irad ortiz, jr.",
    "irad ortiz, jr",
    "irad ortiz jr.",
    "irad ortiz jr",
    "irad ortiz",
    "i. ortiz",
]

# Jose L. Ortiz — all known name variants (lowercase)
_JOSE_VARIANTS = [
    "jose l. ortiz",
    "jose l ortiz",
    "jose ortiz",
    "j. ortiz",
]

# Combined — used by the CD-specific Ortiz boost (Change 1)
ORTIZ_CD_VARIANTS = _IRAD_VARIANTS + _JOSE_VARIANTS

# ── Meet leaders per track ───────────────────────────────────────────────────
# Format: track_code → list of lowercase jockey name variants
# Current as of May 2026 — Churchill Downs spring meet leaders.
MEET_LEADERS = {
    "CD": _IRAD_VARIANTS + _JOSE_VARIANTS,
}

# ── Weak-signal tracks ───────────────────────────────────────────────────────
# Only HIGH CONF top picks get a bet at these tracks.
# MEDIUM or LOW confidence → race is logged and skipped.
WEAK_SIGNAL_TRACKS = {
    "CT",   # Charles Town (WV)
    "DED",  # Delta Downs (LA)
    "EVD",  # Evangeline Downs (LA)
}
