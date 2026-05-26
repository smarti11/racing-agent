import requests, re
resp = requests.get("https://www.nyra.com/aqueduct/racing/entries/", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
matches = list(re.finditer(r"SCR</div>", resp.text))
for m in matches:
    start = max(0, m.start() - 2000)
    chunk = resp.text[start:m.end()]
    prog = re.findall(r"rounded-md.>\s*(\d+)\s*</div>", chunk)
    races = re.findall(r"Race\s+(\d+)", chunk)
    names = re.findall(r">([A-Z][A-Za-z ]+?(?:\([A-Z]+\))?)\s*</div", chunk)
    print("Race:", races[-1] if races else "?", " #:", prog[-1] if prog else "?", " Horse:", names[-1] if names else "?")
