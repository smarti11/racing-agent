# Cursor task: branch consolidation

There are 8 unmerged branches in this repo (`~/agents/racing-agent`), none sharing history with each other, and the working directory has been silently switching between them — that's why S3 dashboard publishing (added in `cursor/dashboard-s3-publish-195f`) disappeared without anyone deleting it: whichever branch happens to be checked out determines what code actually runs. Consolidate before this causes a worse silent regression.

## 1. Merge these into `main`, then check out `main` when done (not a feature branch)

- `cursor/sar-r3-scratch-pick-refresh-2234` — adds `force=` to `save_agent_picks()` and auto-bypasses `POST_TIME_FREEZE` on detected scratches.
- `cursor/saratoga-stub-picks-regen-0a1d` — overnight stub-picks fix.
- `cursor/scratch-refresh-308f` — fresh-DB schema + scratch application on `--once`.
- `cursor/scratch-startup-gate-1a6d` — reboot resilience (LaunchAgents, startup scratch detection), plus two more recent commits on top (`29052f7`, `bb90e2a`) covering calibration/edge fixes and a scratch-source priority fix (mobile-diff vs. late-changes) — include those too.

Flag and resolve any real conflicts as you go rather than force-picking one side blind.

## 2. Hold `cursor/handicapping-gates-195f` out of that merge for now

It and commit `29052f7` on `scratch-startup-gate-1a6d` independently diagnosed the same actionable-bet overconfidence problem two different ways: `handicapping-gates-195f` globally drops `MARKET_BLEND_ALPHA` 0.65→0.45 and adds a new `MARKET_SCORE_BLEND`/`blend_scores_with_market` mechanism; the other branch instead adds a separate, scoped `ACTIONABLE_BLEND_ALPHA=0.10` used only for edge/Kelly sizing, leaving display confidence at 0.65.

Before merging either, run both through the same empirical test in `tools/fit_actionable_alpha.py` (sweeps blend weight against graded `agent_actionable_bets` history, reports Brier score) and report which one the data actually supports — including whether `MARKET_SCORE_BLEND` earns its own weight on top of whichever probability-blend wins. Don't merge on assumption.

## 3. `cursor/poplar-floating-shelves-205e` has zero racing-agent content

It's a woodworking/shelf-install project (finish schedules, milling guides). This looks like a session that got pointed at the wrong repo. Confirm whether that's intentional; if not, move it to wherever that project actually belongs and drop it from this repo's branch list.

## 4. Low priority, whenever convenient

`cursor/dev-environment-setup-e46d` (adds `AGENTS.md` + `pytz` to requirements) is harmless housekeeping, fine to merge into `main` any time.
