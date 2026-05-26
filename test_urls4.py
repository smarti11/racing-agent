import requests

tracks = [
    ("GP", "Gulfstream Park"),
    ("PRX", "Parx Racing"),
    ("MNR", "Mountaineer"),
    ("CT", "Charles Town"),
    ("KEE", "Keeneland"),
    ("OP", "Oaklawn Park"),
]

for code, name in tracks:
    url = "https://mobile.equibase.com/html/entries%s2026041301.html" % code
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
    has_prog = "Program:" in resp.text if resp.status_code == 200 else False
    print("%s [%s]: status=%d  has_entries=%s" % (name, code, resp.status_code, has_prog))
