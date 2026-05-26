"""Compare lifetime/all-data jockey stats vs. 30-day rolling stats for today's
Pick #1 picks. Diagnostic only — does not modify live handicapper."""
from datetime import datetime
import pytz
from db.database import get_conn
from core.form import get_jockey_stats_from_db, get_jockey_recent_win_pct, get_trainer_stats_from_db, get_trainer_recent_win_pct

EASTERN = pytz.timezone("US/Eastern")
today = datetime.now(EASTERN).date().isoformat()

conn = get_conn()
rows = conn.execute("""
    WITH latest AS (
        SELECT 
            aph.race_id, aph.program_num, aph.confidence, aph.horse_name,
            ROW_NUMBER() OVER (
                PARTITION BY aph.race_id 
                ORDER BY aph.rendered_ts DESC
            ) AS rn
        FROM agent_picks_history aph
        JOIN races r ON aph.race_id = r.id
        WHERE r.race_date = ? AND aph.rank = 1
    )
    SELECT 
        r.track_name, r.race_num, l.horse_name, l.program_num, l.confidence,
        e.jockey, e.trainer
    FROM latest l
    JOIN races r ON r.id = l.race_id
    JOIN entries e ON e.race_id = l.race_id AND e.program_num = l.program_num
    WHERE l.rn = 1 AND l.confidence IN ('HIGH', 'MEDIUM')
    ORDER BY r.track_name, r.race_num
""", (today,)).fetchall()

print(f"\n{'Track':<22} {'R':<3} {'Horse':<22} {'Conf':<6} {'Jockey':<22} {'AllW%':>7} {'7dW%':>7} {'Diff':>7}")
print("-" * 110)
for row in rows:
    j = row["jockey"] or ""
    all_data = get_jockey_stats_from_db(j) if j else {}
    recent = get_jockey_recent_win_pct(j, days=7) if j else {}
    a = all_data.get("win_pct")
    r = recent.get("win_pct")
    a_s = f"{a}%" if a else "n/a"
    r_s = f"{r}%" if r else "n/a"
    diff = f"{r-a:+.1f}%" if (a and r) else "—"
    horse = (row["horse_name"] or "")[:20]
    jock = (j or "")[:20]
    print(f'{row["track_name"]:<22} R{row["race_num"]:<2} {horse:<22} {row["confidence"]:<6} {jock:<22} {a_s:>7} {r_s:>7} {diff:>7}')

conn.close()
