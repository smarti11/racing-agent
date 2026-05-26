import requests
import re

resp = requests.get(
    "https://mobile.equibase.com/html/entriesGP20260413.html",
    headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
    timeout=10
)
print("Status: %d" % resp.status_code)
print("\nAll links:")
for m in re.finditer(r'href="([^"]*)"', resp.text):
    print("  %s" % m.group(1))
