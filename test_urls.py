import requests
import re

resp = requests.get(
    "https://mobile.equibase.com/html/entriesGP.html",
    headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
    timeout=10
)
print("Day card page status: %d" % resp.status_code)

# Find all race links
links = re.findall(r'href="([^"]*entries[^"]*)"', resp.text)
print("\nRace links found:")
for link in links[:15]:
    print("  %s" % link)

# Also show the raw HTML around race links
for m in re.finditer(r'<a[^>]*href="([^"]*entries[^"]*\d{2}\.html)"[^>]*>([^<]*)</a>', resp.text):
    print("  Link: %s  Text: %s" % (m.group(1), m.group(2).strip()))
