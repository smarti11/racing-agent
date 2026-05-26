import requests
from bs4 import BeautifulSoup

# Try the regular equibase.com chart URL
urls_to_try = [
    "https://www.equibase.com/premium/eqbPDFChartPlus.cfm?RACE=1&BorP=P&TID=PRX&CTRY=USA&DT=04/14/2026",
    "https://www.equibase.com/static/chart/PDF/PRX041426USA.pdf",
    "https://www.equibase.com/static/chart/PDF/PRX041426USA-EQB.pdf",
    "https://www.equibase.com/premium/chartEmb.cfm?track=PRX&raceDate=04/14/2026&cy=USA",
]

for url in urls_to_try:
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
        print(f"\n{url}")
        print(f"  Status: {resp.status_code}, Length: {len(resp.content)}")
        print(f"  Final URL: {resp.url}")
        if resp.status_code == 200 and len(resp.content) < 5000:
            print(f"  Snippet: {resp.text[:500]}")
    except Exception as e:
        print(f"  ERROR: {e}")
