import requests
import re

# Fetch the main entries page and get the actual track URLs
resp = requests.get(
    "https://mobile.equibase.com/html/entries.html",
    headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
    timeout=10
)

# Find all track links with their full href
for m in re.finditer(r'href="([^"]*entries([A-Z0-9]+)\.html)"[^>]*>([^<]+)</a>', resp.text):
    href = m.group(1)
    code = m.group(2)
    name = m.group(3).strip()
    if name in ["Keeneland", "Oaklawn Park", "Aqueduct", "Gulfstream Park"]:
        full = href if href.startswith("http") else "https://mobile.equibase.com" + href
        print("%s [%s]: %s" % (name, code, full))
        # Fetch and check
        r2 = requests.get(full, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
        print("  status=%d  length=%d" % (r2.status_code, len(r2.text)))
        # Find race links
        links = re.findall(r'href="([^"]*entries[^"]*\d{2}\.html)"', r2.text)
        if links:
            print("  Race links: %s" % links[:3])
            # Test first race
            rl = links[0] if links[0].startswith("http") else "https://mobile.equibase.com" + links[0]
            r3 = requests.get(rl, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=5)
            print("  First race: %s status=%d has_Program=%s" % (rl, r3.status_code, "Program:" in r3.text))
        else:
            print("  No race links found")
            # Show what links ARE there
            all_links = re.findall(r'href="([^"]*)"', r2.text)
            print("  All links: %s" % all_links[:10])
