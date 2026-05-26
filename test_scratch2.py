from db.database import get_conn
from data.equibase import get_race_entries as eq_fetch
from datetime import datetime

conn = get_conn()
races = conn.execute("""
    SELECT r.id, r.track_code, r.track_name, r.race_num
    FROM races r
    WHERE r.race_date = '2026-04-14'
    ORDER BY r.track_name, r.race_num
""").fetchall()

date_str = "20260414"
scratch_count = 0
for race in races:
    db_entries = conn.execute(
        "SELECT program_num, horse_name FROM entries WHERE race_id=?",
        (race[0],)
    ).fetchall()
    db_nums = {e[0] for e in db_entries}

    url = "https://mobile.equibase.com/html/entries%s%s%02d.html" % (race[1], date_str, race[3])
    live = eq_fetch(url, race[1], race[2], race[3], "")
    if live and live.get("entries"):
        live_nums = {e["program_num"] for e in live["entries"]}
        missing = db_nums - live_nums
        if missing:
            for m in missing:
                name = next((e[1] for e in db_entries if e[0] == m), "?")
                print("SCRATCH: %s R%d #%s %s" % (race[2], race[3], m, name))
                scratch_count += 1
    else:
        pass  # page gone, skip silently

conn.close()
print("\nTotal scratches found: %d" % scratch_count)
