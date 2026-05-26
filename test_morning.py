import requests
from datetime import datetime

date_str = datetime.now().strftime('%Y%m%d')
tracks = [
    ("KEE", "Keeneland"), ("OP", "Oaklawn Park"), ("AQU", "Aqueduct"),
    ("GP", "Gulfstream Park"), ("SA", "Santa Anita"), ("LRL", "Laurel Park"),
    ("TAM", "Tampa Bay"), ("CT", "Charles Town"),
]

for code, name in tracks:
    url = "https://mobile.equibase.com/html/entries%s%s01.html" % (code, date_str)
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
        has_entries = "Program:" in resp.text if resp.status_code == 200 else False
        print("%s [%s]: status=%d  entries=%s" % (name, code, resp.status_code, has_entries))
    except Exception as e:
        print("%s [%s]: ERROR %s" % (name, code, e))
