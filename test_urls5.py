import requests
import re
from datetime import datetime

date_str = datetime.now().strftime('%Y%m%d')

for code in ["KEE", "GP", "OP", "AQU"]:
    # Fetch the day card page
    url = "https://mobile.equibase.com/html/entries%s%s.html" % (code, date_str)
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
    print("%s day card [%s]: status=%d" % (code, url, resp.status_code))
    if resp.status_code == 200:
        links = re.findall(r'href="([^"]*entries[^"]*\d+\.html)"', resp.text)
        print("  Links found: %s" % links[:5])
        # Try the first race link directly
        if links:
            race_url = links[0] if links[0].startswith("http") else "https://mobile.equibase.com" + links[0]
            resp2 = requests.get(race_url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
            print("  First race URL: %s  status=%d  has_Program=%s" % (race_url, resp2.status_code, "Program:" in resp2.text))
