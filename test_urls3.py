import requests

# Test the exact URL the parser builds vs the relative path
url1 = "https://mobile.equibase.com/html/entriesGP2026041301.html"
url2 = "https://mobile.equibase.com/html/entriesGP2026041301.html"

resp1 = requests.get(url1, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=10)
print("Full URL status: %d" % resp1.status_code)

# Check if the relative link works
resp2 = requests.get("https://mobile.equibase.com" + "/html/entriesGP2026041301.html", headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=10)
print("Relative URL status: %d" % resp2.status_code)

# Check if it has the green.gif separator (our parser needs this)
if resp1.status_code == 200:
    print("Has green.gif: %s" % ("green.gif" in resp1.text))
    print("Has Program: %s" % ("Program:" in resp1.text))
    print("Content length: %d" % len(resp1.text))
elif resp2.status_code == 200:
    print("Has green.gif: %s" % ("green.gif" in resp2.text))
    print("Has Program: %s" % ("Program:" in resp2.text))
    print("Content length: %d" % len(resp2.text))
else:
    print("BOTH FAILED")
    # Try without the 0 padding
    url3 = "https://mobile.equibase.com/html/entriesGP202604131.html"
    resp3 = requests.get(url3, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"}, timeout=10)
    print("No-pad URL status: %d" % resp3.status_code)
