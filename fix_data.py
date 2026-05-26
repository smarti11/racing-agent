from db.database import get_conn, grade_agent_picks
import pytz
from datetime import datetime
today_et = datetime.now(pytz.timezone("US/Eastern")).date().isoformat()
print("Today (ET):", today_et)
conn = get_conn()
rows = conn.execute("SELECT DISTINCT race_date FROM races ORDER BY race_date DESC LIMIT 5").fetchall()
print("Current race_dates:", [r[0] for r in rows])
if today_et == "2026-04-14":
    cur = conn.execute("UPDATE races SET race_date = ? WHERE race_date = ?", (today_et, "2026-04-15"))
    conn.commit()
    print("Moved", cur.rowcount, "races")
conn.close()
conn = get_conn()
ungraded = conn.execute("SELECT DISTINCT res.race_id, res.winner_num, res.second_num, res.third_num FROM results res JOIN agent_picks ap ON ap.race_id = res.race_id WHERE ap.result IS NULL").fetchall()
conn.close()
for row in ungraded:
    grade_agent_picks(row["race_id"], {"winner_num": row["winner_num"], "second_num": row["second_num"], "third_num": row["third_num"]})
print("Graded", len(ungraded), "races")
