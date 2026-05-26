from db.database import get_conn, get_todays_races, get_race_entries
from data.equibase import get_race_entries as eq_get_entries
from datetime import datetime

conn = get_conn()
races = conn.execute("""
    SELECT r.id, r.track_code, r.track_name, r.race_num
    FROM races r
    WHERE r.race_date = date('now')
    ORDER BY r.track_name, r.race_num
""").fetchall()

date_str = datetime.now().strftime('%Y%m%d')
print("Comparing DB vs live Equibase:")
for race in races:
    db_entries = get_race_entries(race[0])
    db_nums = {e["program_num"] for e in db_entries}

    url = "https://mobile.equibase.com/html/entries%s%s%02d.html" % (race[1], date_str, race[3])
    live = eq_get_entries(url, race[1], race[2], race[3], "")
    if live:
        live_nums = {e["program_num"] for e in live.get("entries", [])}
        missing = db_nums - live_nums
        if missing:
            print("  %s R%d: SCRATCH DETECTED - missing #%s" % (race[2], race[3], ", #".join(missing)))
    else:
        print("  %s R%d: page gone (racing finished)" % (race[2], race[3]))

conn.close()
print("Done")
