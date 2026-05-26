-- ============================================================================
-- DRF Chart Parser - Schema Additions
-- Adds 6 new tables to racing.db for chart-derived data
-- Safe to run multiple times (uses CREATE TABLE IF NOT EXISTS)
-- ============================================================================

-- 1. Per-race chart metadata (joins to existing `races` table by track+date+race_num)
CREATE TABLE IF NOT EXISTS chart_races (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id         INTEGER,                -- nullable; links to races.id if matched
    track_code      TEXT NOT NULL,
    race_date       TEXT NOT NULL,
    race_num        INTEGER NOT NULL,
    distance_raw    TEXT,                   -- "5½ FURLONGS"
    surface         TEXT,                   -- "Turf" | "Dirt" | "AW"
    race_type       TEXT,                   -- "ALLOWANCE OPTIONAL CLAIMING" | "MAIDEN SPECIAL WEIGHT" | etc
    purse           INTEGER,                -- 58000
    conditions_raw  TEXT,                   -- full conditions text
    weather         TEXT,                   -- "Clear. 69."
    track_condition TEXT,                   -- "firm" | "fast" | "good" | "sloppy"
    off_time        TEXT,                   -- "10:34"
    start_note      TEXT,                   -- "Won driving." or "Won ridden out."
    fetched_ts      TEXT NOT NULL,
    parsed_ts       TEXT NOT NULL,
    UNIQUE(track_code, race_date, race_num),
    FOREIGN KEY(race_id) REFERENCES races(id)
);

-- 2. Per-horse result line (replaces what we lost from incomplete entry parsing)
CREATE TABLE IF NOT EXISTS chart_horses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_race_id       INTEGER NOT NULL,
    program_num         TEXT NOT NULL,
    horse_name          TEXT NOT NULL,
    last_raced_raw      TEXT,           -- e.g. "12ß26 ¬Lrl§" (last race ref)
    equipment           TEXT,           -- "L b" / "L bf" / "b" (lasix/blinkers/etc)
    age                 INTEGER,
    weight              INTEGER,
    post_position       INTEGER,
    start_position      INTEGER,
    calls_raw           TEXT,           -- raw position calls e.g. "3¦ 2Ç 2¦ 1Ç"
    finish_position     INTEGER,        -- 1-N
    finish_margin_raw   TEXT,           -- raw margin at finish (e.g. "1Ç" = head)
    jockey              TEXT,
    claim_price         INTEGER,        -- nullable, only for claiming races
    odds                REAL,           -- 4.00 = 4-1
    is_winner           INTEGER DEFAULT 0,
    FOREIGN KEY(chart_race_id) REFERENCES chart_races(id)
);

-- 3. Fractional times (decimal seconds)
CREATE TABLE IF NOT EXISTS chart_fractions (
    chart_race_id   INTEGER PRIMARY KEY,
    frac_1          REAL,               -- :22.12
    frac_2          REAL,               -- :44.62 (half mile)
    frac_3          REAL,               -- :56.00
    frac_4          REAL,               -- 1:01.90
    frac_5          REAL,               -- (route races have 5)
    final_time      REAL,               -- final time in seconds
    raw_text        TEXT,               -- full TIME line for debugging
    FOREIGN KEY(chart_race_id) REFERENCES chart_races(id)
);

-- 4. Win/Place/Show + exotic payouts
CREATE TABLE IF NOT EXISTS chart_payouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_race_id   INTEGER NOT NULL,
    bet_type        TEXT NOT NULL,      -- WIN, PLACE, SHOW, EXACTA, TRIFECTA, SUPERFECTA, DD, PICK3, PICK4, PICK5
    program_nums    TEXT,               -- "2" or "2-7" or "2-7-5-1"
    base_amount     REAL,               -- $2, $1, $0.50
    payout          REAL,               -- dollar payout
    pool_size       REAL,               -- mutuel pool (if available)
    FOREIGN KEY(chart_race_id) REFERENCES chart_races(id)
);

-- 5. Trip notes per horse (the gold)
CREATE TABLE IF NOT EXISTS chart_trips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_race_id   INTEGER NOT NULL,
    horse_name      TEXT NOT NULL,
    program_num     TEXT,
    trip_raw        TEXT NOT NULL,      -- the full narrative for this horse
    running_style   TEXT,               -- E (early) / P (presser) / S (stalker) / C (closer)
    trouble_score   TEXT,               -- CLEAN | MINOR | MAJOR
    trouble_tags    TEXT,               -- JSON array: ["bumped_start", "steadied", "wide_trip"]
    pace_role       TEXT,               -- "set pace" | "dueled" | "stalked" | "off pace" | "closer"
    trip_notes_summary TEXT,            -- one-line summary for quick review
    FOREIGN KEY(chart_race_id) REFERENCES chart_races(id)
);

-- 6. Scratched horses (also captured in main scratches table, but stored here for completeness)
CREATE TABLE IF NOT EXISTS chart_scratches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_race_id   INTEGER NOT NULL,
    horse_name      TEXT NOT NULL,
    last_raced_raw  TEXT,
    FOREIGN KEY(chart_race_id) REFERENCES chart_races(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chart_races_date ON chart_races(race_date);
CREATE INDEX IF NOT EXISTS idx_chart_races_track_date ON chart_races(track_code, race_date);
CREATE INDEX IF NOT EXISTS idx_chart_horses_race ON chart_horses(chart_race_id);
CREATE INDEX IF NOT EXISTS idx_chart_horses_name ON chart_horses(horse_name);
CREATE INDEX IF NOT EXISTS idx_chart_trips_name ON chart_trips(horse_name);
CREATE INDEX IF NOT EXISTS idx_chart_trips_trouble ON chart_trips(trouble_score);
CREATE INDEX IF NOT EXISTS idx_chart_payouts_race ON chart_payouts(chart_race_id);
