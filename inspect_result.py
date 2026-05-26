import requests
from bs4 import BeautifulSoup

# Grab any recent results page to see the format
url = "https://mobile.equibase.com/html/resultsPRX2026041401.html"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=10)
print("Status:", resp.status_code, "Length:", len(resp.text))
print("=" * 60)
print("FULL TEXT:")
print("=" * 60)
print(BeautifulSoup(resp.text, "html.parser").get_text())
print("=" * 60)
print("RAW HTML (first 3000 chars):")
print("=" * 60)
print(resp.text[:3000])
