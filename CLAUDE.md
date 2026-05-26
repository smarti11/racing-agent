# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Known Issues

**Issue 1 — Stale picks from overnight stub data (fixed 2026-05-25):** Equibase's mobile endpoint returns a partial card overnight, often only 2–3 horses per race. The agent runs at midnight, generates picks against this stub, and stamps them `TAINTED_PARSE`. Two fixes now address this: (1) **TAINTED_PARSE regeneration** — at the top of the pick-save loop, if the existing rank-1 pick is `TAINTED_PARSE`, active entries have grown to ≥4, and no result has been posted, `_force_regen=True` is set, the freeze is bypassed, and the stale picks are archived to `agent_picks_history` with trigger `tainted_parse_superseded` before re-handicapping. (2) **POST_TIME_FREEZE PM fix** — bare post times like `"1:30"` were previously parsed as 01:30 AM, causing the freeze to fire ~12 hours early and leaving all picks frozen with stub data until race day; see the POST_TIME_FREEZE note below. The `first_fetched_ts` column (added 2026-05-25) preserves the original insert time and is the primary diagnostic for detecting stub-data picks. Confirmed affected 2026-05-25: BAQ R8, CBY R3, MTH R2.

**Issue 2 — Parser silent-drop risk (lower frequency, unconfirmed):** The entry parser in `data/equibase.py` has two silent-drop paths: chunks without a `Program:` line (~line 211, `if not prog_m: continue`) and chunks where no `<b>horse name</b>` tag is found (~line 246, `if entry["horse_name"]:`). These could account for the historical Keeneland Race 8 case (6 of 11 runners captured on 2026-04-11, pre-DB-reset, not reproducible). As of 2026-05-25 the parser emits `WARNING` logs on every silent drop including the chunk index and a 200-char HTML snippet, so any recurrence will be diagnosable from `logs/racing.log`.

## Running the Agent

```bash
# Activate virtualenv first (always required)
source venv/bin/activate

# Single fetch + dashboard then exit
python racing_agent.py --once

# List tracks racing today
python racing_agent.py --tracks

# Print card to terminal (entries must already be fetched)
python racing_agent.py --card

# Regenerate dashboard only
python racing_agent.py --dashboard

# Run continuously (default — refreshes every 5-10 min)
python racing_agent.py
```

Dashboard is served at `http://100.68.82.83:8081/racing.html` (iPhone-accessible). The agent starts a static file server on port 8081 and a scratch override server on port 8082 automatically when run in continuous mode.

To force a dashboard regeneration without restarting the agent, touch `~/.regen_now` — the main loop checks for this flag every 30 seconds.

## Architecture

The agent runs as a single long-lived Python process with no external task queue. All state lives in SQLite (`db/racing.db`). The agent backs up this file daily to `backups/`.

### Module Map

| Module | Purpose |
|---|---|
| `racing_agent.py` | Entry point; main loop, orchestrates all phases |
| `config/settings.py` | Intervals, handicapping weights, track lists, excluded tracks |
| `config/meet_leaders.py` | Per-meet jockey multipliers (e.g., Ortiz at Churchill) |
| `data/equibase.py` | Scrapes Equibase mobile (`mobile.equibase.com`) for entries and scratches. **Parser note:** entry splitting uses the green separator image, not plain text — splitting on plain text causes odd-only horse capture, do not change. **Scratch detection note:** `get_scratches()` compares live entries against DB records because Equibase mobile silently removes scratched horses rather than marking them SCR; the desktop endpoint behaves differently (explicit SCR markers). |
| `data/results.py` | Fetches race results for grading picks |
| `data/chart_fetcher.py` + `chart_parser.py` | Downloads and parses past performance charts |
| `data/speed_calc.py` | Computes speed figures from chart data |
| `db/database.py` | All SQLite reads/writes; schema defined in `init_db()` |
| `core/handicapper.py` | Main scoring engine; combines speed, jockey, trainer, class, pace, form |
| `core/speed_figures.py` | Speed figure estimates from morning-line odds when chart data unavailable |
| `core/pace.py` | Pace scenario analysis (front-runner, presser, closer) |
| `core/form.py` | Form analysis — last 3 finishes, days since last race, jockey/trainer DB stats |
| `core/probabilities.py` | Softmax win probabilities over active horses (Benter 1994, temperature=8.0) |
| `core/calibrator.py` | Isotonic regression (PAV algorithm) to calibrate raw probabilities against outcomes |
| `core/kelly.py` | Quarter-Kelly bet sizing with $2 min / $20 max caps |
| `core/bolton_chapman.py` | Academic guardrails — Bolton-Chapman (1986) MIN_PROBABILITY=0.10 and EV filter |
| `core/pick4_picker.py` | Pick 3/4 sequence recommendations using top-2 per leg |
| `core/scratch_fetcher.py` | Real-time scratch detection from Equibase late-changes feed |
| `dashboard/builder.py` | Generates `dashboard/racing.html` — the mobile dashboard |
| `dashboard/jockey_analytics.py` | Jockey stats section of dashboard |
| `scratch_server.py` | HTTP server (port 8082) accepting `POST /scratch` for manual scratch overrides |
| `tools/` | One-time migration and backfill scripts — not part of normal operation |

### Observability

**Equibase parser (per race, `INFO`):** `Equibase parse [track R#]: N chunks, M matched Program:, K horses extracted` — emitted by `data/equibase.py` after every race parse. If N > M, a chunk had no `Program:` line and was dropped. If M > K, a matched chunk had no `<b>horse name</b>` and was dropped. Either divergence is a silent-drop event.

**Equibase parser (per dropped chunk, `WARNING`):** Includes the chunk index and first 200 chars of the raw HTML. Search `logs/racing.log` for `"Equibase parse drop"` to find any occurrence.

**Entry audit (per race after picks save, `INFO`):** `Entry audit TRACK R#: N entries (M active) | first_fetched=... last_fetched=... | picks_created=...` — emitted by `racing_agent.py`. When `first_fetched` is close to `picks_created` and far from `last_fetched`, the race was handicapped against overnight stub data. This is the primary indicator for Issue 1 above.

### Data Flow

1. **Entries** — `data/equibase.py` scrapes Equibase mobile → `db/database.save_race()` / `save_entry()`
2. **Handicapping** — `core/handicapper.handicap_race()` scores each horse → `core/probabilities.scores_to_probabilities()` → softmax win probs → `core/calibrator` applies isotonic calibration if `models/calibrator_pick1.json` exists
3. **Picks saved** — `save_agent_picks()` writes ranked picks with score, win_prob, morning_line, calibrated_prob, and data_quality flag
4. **Results** — `data/results.py` → `db.save_result()` → `db.grade_agent_picks()` retroactively scores pick accuracy
5. **Dashboard** — `dashboard/builder.py` reads all today's data from DB and renders `dashboard/racing.html`

### Key Design Decisions

**Time gates on scratch detection** — Equibase returns stale overnight data with false scratch indicators before 7 AM ET. Two separate gates enforce this: `FETCH_SCRATCH_GATE` (in entry fetching, skips marking scratches before 7 AM) and `SCRATCH_TIME_GATE` (in `check_scratches()`, skips before 10 AM). Canadian tracks (WO, WOT, WOD, HST, GLD) use the mobile endpoint; all others use the desktop endpoint which shows explicit SCR markers.

**POST_TIME_FREEZE** — picks are not saved or updated within 30 minutes of a race's post time. Races with results already in DB are also skipped. This prevents stale/tainted picks from appearing post-race. **Post time AM/PM assumption (fixed 2026-05-25):** Equibase stores post times without AM/PM (e.g., `"1:30"`). The freeze parser now treats bare times with `_hr < 8` as PM (`_hr += 12`), so `"1:30"` → 13:30 and the freeze fires at 13:00 instead of 01:00 AM. Before this fix, all picks for afternoon races were effectively frozen from ~01:00 AM onward, leaving stale overnight picks in `agent_picks` all day and causing the dashboard summary and per-race drill-in to show different horses and confidence levels.

**Dashboard render / agent_picks_history write gate (fixed 2026-05-26):** `dashboard/builder.py` re-runs `handicap_race()` live at render time for every race, including completed ones. Before this fix, the result was always written to `agent_picks_history` regardless — the `_race_done` flag only changed the trigger label from `"dashboard_render"` to `"dashboard_render_postrace"`, it did not prevent the write. This caused post-race re-computations (on shifted entry odds or transient scratch states) to overwrite the actual pre-race pick record in `agent_picks_history`, making the drill-in show the wrong horse as the historical pick. Fix: `agent_picks_history` is now only written when `not _race_done`. Completed races still re-render for display but no longer persist. The `"dashboard_render_postrace"` trigger string no longer appears in new writes; rows with that trigger in the DB are pre-fix artifacts.

**DATA_QUALITY flags** — every set of picks is tagged `OK`, `TAINTED_SCRATCH` (fewer than 3 active horses), or `TAINTED_PARSE` (fewer than 4 total entries). These propagate to the dashboard.

**Handicapping weights** (configurable in `config/settings.py`):
- Speed figures: 35%, Jockey win %: 20%, Trainer win %: 20%, Class: 15%, Pace: 10%

**Probability calibration** — the `IsotonicCalibrator` in `core/calibrator.py` uses PAV algorithm. It only activates if `models/calibrator_pick1.json` exists (built by separate training scripts in `tools/`). Without it, raw softmax probabilities are used.

**Pick 3/4 strategy** — `core/pick4_picker.py` uses top-2 horses per leg (2^N combos × $0.50), filters out LOW confidence legs, and applies Bolton-Chapman EV check using track-average historical payouts from the `pick_payouts` table.

**Betting strategy** — Current production strategy on HIGH confidence picks: $2 WIN + EXACTA BOX.

**Performance baseline — DATA INTEGRITY WARNING:** All performance data collected before 2026-05-26 (including the May 14 snapshot below) was generated against overnight stub fields of 2–3 horses per race due to the POST_TIME_FREEZE AM/PM bug. The handicapper was never actually scoring full fields — it was picking from a 2–3 horse subset at midnight and those picks were frozen by a misread freeze for the rest of the day. Any ROI figures, win percentages, confidence-level breakdowns, or weight-tuning conclusions drawn from this data are artifacts of the bug, not signals about handicapping quality. **Do not use pre-2026-05-26 stats as a calibration baseline or to justify threshold/weight changes.**

2026-05-26 is the first day with correct full-field handicapping. Allow ~2 weeks of clean data (roughly 2026-06-09) to accumulate before drawing any conclusions about strategy performance or adjusting weights, thresholds, or confidence cutoffs.

May 14, 2026 snapshot (tainted — retained for reference only): 131 races, $522.00 wagered, $331.16 returned, -$190.84 net, -36.8% ROI. Top Pick 3: Belmont At The Big A R5-8 EV +$37.72. Note: database was also reset in April 2026 to eliminate corrupted historical data — do not include pre-reset data in performance queries.

### Database Schema (db/racing.db)

Tables: `races`, `entries`, `odds`, `picks`, `jockey_stats`, `agent_picks`, `results`, `pick_payouts`, `manual_scratches`. Schema is in `db/database.init_db()`.

The `entries` table has two timestamp columns: `fetched_ts` (overwritten on every re-fetch) and `first_fetched_ts` (TEXT, nullable — set on initial INSERT, intentionally excluded from the `ON CONFLICT DO UPDATE` clause so it is never overwritten). Rows inserted before 2026-05-25 have `first_fetched_ts` backfilled to match `fetched_ts`; true first-fetch timestamps for those rows were lost to the prior overwrite behavior.

A separate `db/picks.db` exists for historical pick tracking via `pick_tracker.py`.

### Ports

| Port | Service |
|---|---|
| 8081 | Static file server — serves `dashboard/racing.html` |
| 8082 | Scratch override server (`scratch_server.py`) — accepts `POST /scratch {race_id, program_num}` |