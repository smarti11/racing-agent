from data.equibase import get_day_card, get_race_entries
from datetime import datetime
import requests

date_str = datetime.now().strftime('%Y%m%d')

races = get_day_card("GP", "Gulfstream Park", date_str)
print("Gulfstream day card: %d races" % len(races))
if races:
    for r in races[:3]:
        print("  Race %d URL: %s" % (r["race_num"], r["url"]))
        result = get_race_entries(r["url"], "GP", "Gulfstream Park", r["race_num"], r["post_time"])
        if result:
            print("    Entries: %d" % len(result.get("entries", [])))
        else:
            print("    FAILED - no entries returned")
            resp = requests.get(r["url"], headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=10)
            print("    HTTP status: %d, length: %d" % (resp.status_code, len(resp.text)))
            print("    First 200 chars: %s" % resp.text[:200])
