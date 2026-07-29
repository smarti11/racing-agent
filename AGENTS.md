# AGENTS.md

See `CLAUDE.md` for the full architecture, module map, and the canonical run
commands (`README.md` also documents setup). This file only adds Cursor Cloud
environment guidance.

## Cursor Cloud specific instructions

### What this app is
A single long-lived Python process that scrapes Equibase mobile for daily
Thoroughbred entries, handicaps each race, generates picks, and renders a
mobile dashboard (`dashboard/racing.html`). All state is SQLite at
`db/racing.db`. There is no external service dependency.

### Running / serving (see CLAUDE.md for the full list)
- One-shot pipeline: `venv/bin/python racing_agent.py --once` (fetch entries →
  handicap → save picks → build dashboard, then exit). Use this to validate the
  environment; it exercises the full core flow.
- Serve the dashboard: `./serve_dashboard.sh` (static server on port 8081,
  serves `dashboard/racing.html`). `racing_agent.py` continuous mode does NOT
  start the HTTP server itself in this environment — it's normally run by
  launchd on the production Mac; use `serve_dashboard.sh` here.
- `dashboard/racing.html` is a read-only generated artifact (gitignored).

### Database schema gotcha (IMPORTANT — non-obvious)
`db/database.init_db()` does NOT produce a complete schema for a *fresh*
`db/racing.db`. The production DB was built up incrementally via the
`tools/migrate_*.py` scripts, and several pieces are missing from `init_db()`:
- `entries` lacks `UNIQUE(race_id, program_num)` → `save_entry()`'s
  `ON CONFLICT(race_id, program_num)` fails with "ON CONFLICT clause does not
  match any PRIMARY KEY or UNIQUE constraint" and NO entries get saved.
- `agent_picks` is missing `score`, `win_prob`, `morning_line`,
  `calibrated_prob`, `data_quality` → pick pipeline fails with
  "no such column: data_quality".
- The `agent_picks_history` table is never created at all (migrations assume it
  already exists).

The runtime `db/racing.db` in this environment's snapshot has ALREADY been
healed, so normal runs work. Only re-apply the heal below if `db/racing.db` is
deleted/recreated (a fresh `init_db()` will re-introduce the broken schema).
Do NOT run the `tools/migrate_*.py` scripts to fix this — they patch source
files and kill processes; the source is already at the latest version.

One-time DB schema heal (safe / idempotent):
```bash
venv/bin/python - <<'PY'
from db.database import init_db, get_conn
init_db()
with get_conn() as c:
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_race_prog ON entries(race_id, program_num)")
    for col, typ in [("score","REAL"),("win_prob","REAL"),("morning_line","TEXT"),
                     ("calibrated_prob","REAL"),("data_quality","TEXT DEFAULT 'OK'")]:
        try: c.execute(f"ALTER TABLE agent_picks ADD COLUMN {col} {typ}")
        except Exception: pass
    c.execute("""CREATE TABLE IF NOT EXISTS agent_picks_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, race_id INTEGER NOT NULL,
        rank INTEGER NOT NULL, program_num TEXT NOT NULL, horse_name TEXT NOT NULL,
        confidence TEXT, role TEXT, rendered_ts TEXT NOT NULL, trigger TEXT,
        data_quality TEXT DEFAULT 'UNVERIFIED', FOREIGN KEY(race_id) REFERENCES races(id))""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_aph_race ON agent_picks_history(race_id)")
PY
```

### Network expectations
- Equibase mobile scraping (entries/results/charts) works from the VM.
- Live-odds sources (TVG / TwinSpires) are blocked by bot protection — logs show
  `Live odds: <TRACK> blocked by bot protection`. This is expected and
  non-fatal; picks are still generated (odds enrichment is optional).
- Equibase parse logs `WARNING ... chunk 0 has no Program: line` for every race:
  chunk 0 is the DOCTYPE header and is expected to be dropped. It is a silent
  drop only when `matched Program:` < `chunks - 1`.

### Data is date-dependent
The pipeline handicaps *today's* live card, so counts (tracks/races/picks) vary
by day and by time of day (races within 30 min of post time are frozen and
skipped). An empty-ish result late at night is normal, not a bug.

### Lint / test / build
- No linter, formatter, or automated test framework is configured (the
  top-level `test_*.py` files are ad-hoc scraping probes, not a test suite).
- Build/syntax sanity check: `venv/bin/python -m compileall config core data db dashboard racing_agent.py`.
