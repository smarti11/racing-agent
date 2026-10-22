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
2. **Handicapping** — `core/handicapper.handicap_race()` scores each horse → `core/probabilities.scores_to_probabilities()` → softmax win probs (`win_prob`, raw) → `core/anchored_model` computes morning-line-anchored probabilities (`calibrated_prob` = `final_prob`) and picks are ranked by them; falls back to raw-score ranking if `models/anchored_weights.json` is missing
3. **Picks saved** — `save_agent_picks()` writes ranked picks with score, win_prob, morning_line, calibrated_prob, and data_quality flag; `save_agent_entry_scores()` writes full per-horse handicap output for all active runners; `save_agent_race_analysis()` writes race-level pace scenario — all three in the same freeze-gated block
4. **Results** — `data/results.py` → `db.save_result()` → `db.grade_agent_picks()` retroactively scores pick accuracy
5. **Dashboard** — `dashboard/builder.py` reads all today's data from DB (picks from `agent_picks`, rich display data from `agent_entry_scores` + `agent_race_analysis`) and renders `dashboard/racing.html`. No computation or writes occur at render time.

### Key Design Decisions

**Time gates on scratch detection** — Equibase returns stale overnight data with false scratch indicators before 7 AM ET. Two separate gates enforce this: `FETCH_SCRATCH_GATE` (in entry fetching, skips marking scratches before 7 AM) and `SCRATCH_TIME_GATE` (in `check_scratches()`, skips before 10 AM). Canadian tracks (`CANADIAN_TRACKS`: WO, WOT, WOD, HST, GLD, CTD, FE, GPR) use the mobile endpoint; all others use the desktop endpoint which shows explicit SCR markers.

**POST_TIME_FREEZE** — picks are not saved or updated within 30 minutes of a race's post time. Races with results already in DB are also skipped. This prevents stale/tainted picks from appearing post-race. **Post time AM/PM assumption (fixed 2026-05-25):** Equibase stores post times without AM/PM (e.g., `"1:30"`). The freeze parser now treats bare times with `_hr < 8` as PM (`_hr += 12`), so `"1:30"` → 13:30 and the freeze fires at 13:00 instead of 01:00 AM. Before this fix, all picks for afternoon races were effectively frozen from ~01:00 AM onward, leaving stale overnight picks in `agent_picks` all day and causing the dashboard summary and per-race drill-in to show different horses and confidence levels.

**Post-time lock and track time zones (2026-10-16):** Equibase post times are *track-local* with no AM/PM (SA "1:00" = 4:00 PM ET; CT "10:02" = 10:02 PM). `db.race_post_time_et()` converts them using `TRACK_TIMEZONES` in `config/settings.py` (unlisted = Eastern) and infers AM/PM from the card's race order (first race 1–9 → PM, 10–11 → AM; each later race is the first reading not earlier than the previous one). The old fixed `hour < 8 → PM` rule froze western tracks hours early and evening races of 8 PM+ from the morning on. Once scheduled post passes, picks are **locked**: `save_todays_picks()` skips the race, `refresh_race_picks()` refuses, and `save_agent_picks()` won't modify `agent_picks` even with `force=True`. Before this, scratch-forced saves rewrote graded picks mid-race (GP R5 2026-10-16). Scratch changes still bypass the 30-minute freeze up to post time.

**Late-changes reversals (2026-10-16):** `core/scratch_fetcher.parse_late_changes()` replays each horse's rows in order. Follow-up rows have no PGM/Horse cells and belong to the horse above them, and the last status wins. "Will Run (Previously Reported as scratched)" un-scratches a horse, but only one whose scratch came from `late_changes` itself (GP R5 Sass Sass, 2026-10-16: reported scratched at 2:30, reversed at 2:33, ran 2nd).

**Canadian exotic names and bases (2026-10-19):** Canadian results pages call the exacta "Exactor" and the trifecta "Triactor". `data/results.py` only matched "Exacta"/"Trifecta" before this, so every Fort Erie result was saved with NULL exotic payouts, which the ROI code reads as "no pool". `tools/backfill_exotics_from_charts.py --track FE --write` fills the NULLs from the chart PDFs. Chart PDFs give the base wagers: WO and FE use a $1 exacta and $0.20 trifecta, and CTD a $2 exacta and $0.50 trifecta. Eureka (EUR) is excluded: it runs a mixed Paint/QH/TB card, and Equibase publishes its entries but no results or charts. Evangeline (EVD) and Albuquerque (ALB) were excluded at the user's request on 2026-10-22. `get_todays_races()` also filters `EXCLUDED_TRACKS`, so a newly excluded track's card that was already loaded drops off the same day.

**Dashboard render / agent_picks_history write gate (fixed 2026-05-26):** `dashboard/builder.py` previously re-ran `handicap_race()` live at render time for every race. This caused post-race re-computations to overwrite the actual pre-race pick record in `agent_picks_history`, making the drill-in show the wrong horse as the historical pick. Fix (2026-05-26, commit 2cb2840): the live re-handicap was removed entirely from the renderer. `dashboard/builder.py` is now fully read-only — it reads picks from `agent_picks` and rich handicap data from `agent_entry_scores` / `agent_race_analysis` (see Option C below). No writes to `agent_picks_history` occur from the renderer under any circumstances. The `"dashboard_render"` and `"dashboard_render_postrace"` trigger strings no longer appear in new writes; rows with those triggers in the DB are pre-fix artifacts.

**Option C — Persist handicap output for read-only dashboard (2026-05-26, commit ea72513):** Removing the live re-handicap from the renderer initially caused the loss of per-horse display fields (pace role, form, days since last race, J%/T%, score bars, value/class/trainer-hot flags) and race-level pace scenario banners. Option C restores full information density without re-introducing any writeback path. Two new tables persist the `handicap_race()` output alongside `save_agent_picks()`:
- `agent_entry_scores` — one row per active runner per race; stores `score`, `speed_fig`, `pace_role`, `form`, `days_since`, `layoff_flag`, `class_change`, `trainer_hot`, `value`, `j_win_pct`, `t_win_pct`. Written by `save_agent_entry_scores()` in `db/database.py`, called from `racing_agent.py` inside the same freeze-gated block as `save_agent_picks()`.
- `agent_race_analysis` — one row per race; stores `pace_scenario_name`, `pace_scenario_notes`, `pace_post_bias`, `lone_speed`. Written by `save_agent_race_analysis()`, same gating.
- `dashboard/builder.py` reads both tables via `get_todays_entry_scores()` and `get_todays_race_analyses()` (one query each per dashboard render). The renderer contains zero write calls.
- Rows in both tables are empty for races handicapped before this commit; they populate on subsequent `save_todays_picks()` cycles.

**DATA_QUALITY flags** — every set of picks is tagged `OK`, `TAINTED_SCRATCH` (fewer than 3 active horses), or `TAINTED_PARSE` (fewer than 4 total entries). These propagate to the dashboard.

**Handicapping weights** (configurable in `config/settings.py`):
- Speed figures: 35%, Jockey win %: 20%, Trainer win %: 20%, Class: 15%, Pace: 10%

**Probability model (2026-10-16)** — `core/anchored_model.py` is a conditional logit with the morning-line implied probability as the prior and the handicapper's features (speed fig, J%/T%, last finish, class change, trainer form, pace role; continuous ones z-scored within race) as adjustments. Picks 1-3 are the top 3 by this probability; rank-1 confidence comes from its probability using cutoffs stored with the weights; the WEAK_SIGNAL_TRACKS HIGH-only rule still applies. Weights live in `models/anchored_weights.json` (gitignored, per-machine) — fit with `python tools/fit_anchored_model.py --write` (pure Python, ~2 min) and re-run monthly. Out-of-sample on 2026-09-01..10-15 (3,183 races): rank-1 win 32.2% vs 24.1% for the old score ranking, log loss 1.719 vs 1.732 for the morning line alone. It replaced the isotonic calibrator (`core/calibrator.py`, no longer called): that was fit on rank-1 picks only and, applied to whole fields, mapped longshots to 0%, everything mid-range to a ≥12.5% floor and the top to 100%.

**Pick 3/4 strategy** — `core/pick4_picker.py` uses top-2 horses per leg (2^N combos × $0.50), filters out LOW confidence legs, and applies Bolton-Chapman EV check using track-average historical payouts from the `pick_payouts` table.

**Rolling doubles (2026-10-19)** — the dashboard's "Rolling Doubles" panel lists a top-3 × top-3 daily double (9 combos at the track's base, `DAILY_DOUBLE_BASE` in settings) for each consecutive race pair at `ROLLING_DOUBLE_TRACKS` (GP, LRL, FL), with live status and a 30-day settled record (`db.get_rolling_doubles()` / `get_rolling_double_record()`). The 9/1–10/19 backtest across all tracks was −8.9% ROI over 2,520 doubles (38% hits). GP (+42%) and LRL (+27%) were best, and TDN, FE, PRX, PID, KEE, WRD, MNR and BTP lost 40–60%. A DD payout is stored on the second leg's result row. WO and SA were dropped 2026-10-22: the new model's top 3 matches the morning-line top 3 in ~83% of races, and ML top-3 doubles over 9/1–10/21 lost 36% (WO) and 29% (SA) while GP (+34%) and LRL (+10%) held up. FL was added 2026-10-21 and is priced at the user's $1 per combo ($9 a ticket) via `ROLLING_DOUBLE_STAKE`; payouts are scaled from the $2 chart base. The older "Daily Double performance" section tracks rank-1 × rank-1 only.

**Betting strategy** — Current production strategy on HIGH confidence picks: $2 WIN + EXACTA BOX.

**Performance baseline — DATA INTEGRITY WARNING:** All performance data collected before 2026-05-26 (including the May 14 snapshot below) was generated against overnight stub fields of 2–3 horses per race due to the POST_TIME_FREEZE AM/PM bug. The handicapper was never actually scoring full fields — it was picking from a 2–3 horse subset at midnight and those picks were frozen by a misread freeze for the rest of the day. Any ROI figures, win percentages, confidence-level breakdowns, or weight-tuning conclusions drawn from this data are artifacts of the bug, not signals about handicapping quality. **Do not use pre-2026-05-26 stats as a calibration baseline or to justify threshold/weight changes.**

2026-05-26 is the first day with correct full-field handicapping. Allow ~2 weeks of clean data (roughly 2026-06-09) to accumulate before drawing any conclusions about strategy performance or adjusting weights, thresholds, or confidence cutoffs.

May 14, 2026 snapshot (tainted — retained for reference only): 131 races, $522.00 wagered, $331.16 returned, -$190.84 net, -36.8% ROI. Top Pick 3: Belmont At The Big A R5-8 EV +$37.72. Note: database was also reset in April 2026 to eliminate corrupted historical data — do not include pre-reset data in performance queries.

### Database Schema (db/racing.db)

Tables: `races`, `entries`, `odds`, `picks`, `agent_picks`, `agent_picks_history`, `agent_entry_scores`, `agent_race_analysis`, `results`, `pick_payouts`, `manual_scratches`. Schema is in `db/database.init_db()`.

Jockey/trainer win% are **not** stored in a dedicated stats table — `core/form.py`'s `get_jockey_stats_from_db()` / `get_trainer_stats_from_db()` compute them live from `entries` + `races` + `results` on every call (≥5 starts required, else falls back to the elite-jockey/trainer list or a default). A `jockey_stats` table existed in the schema through 2026-08 but was dead code — nothing ever wrote to it and the handicapper read from the live query instead; it was removed.

The `entries` table has two timestamp columns: `fetched_ts` (overwritten on every re-fetch) and `first_fetched_ts` (TEXT, nullable — set on initial INSERT, intentionally excluded from the `ON CONFLICT DO UPDATE` clause so it is never overwritten). Rows inserted before 2026-05-25 have `first_fetched_ts` backfilled to match `fetched_ts`; true first-fetch timestamps for those rows were lost to the prior overwrite behavior.

A separate `db/picks.db` exists for historical pick tracking via `pick_tracker.py`.

### Ports

| Port | Service |
|---|---|
| 8081 | Static file server — serves `dashboard/racing.html` |
| 8082 | Scratch override server (`scratch_server.py`) — accepts `POST /scratch {race_id, program_num}` |