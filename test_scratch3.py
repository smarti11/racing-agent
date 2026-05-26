from db.database import get_conn
import requests
from datetime import datetime

conn = get_conn()
races = conn.execute("""
    SELECT r.track_code, r.track_name, r.race_num
    FROM races r
    WHERE r.race_date = '2026-04-14'
    ORDER BY r.track_name, r.race_num
""").fetchall()

live = 0
gone = 0
for race in races:
    url = "https://mobile.equibase.com/html/entries%s20260414%02d.html" % (race[0], race[2])
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
    if resp.status_code == 200 and "Program:" in resp.text:
        print("LIVE: %s R%d" % (race[1], race[2]))
        live += 1
    else:
        gone += 1

conn.close()
print("\nLive: %d  Gone: %d" % (live, gone))
