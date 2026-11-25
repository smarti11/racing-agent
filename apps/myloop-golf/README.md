# MyLoop Golf — myloop.golf

Public homepage for **MyLoop Golf**: Course App (everyday GPS + scoring) and Outing App (tournament / shotgun day).

## Local preview

```bash
cd apps/myloop-golf
python3 -m http.server 8080 --bind 127.0.0.1
# open http://127.0.0.1:8080
```

## Deploy (Cloudflare Worker)

```bash
cd ~/racing-agent/apps/myloop-golf
npx wrangler deploy
```

Point **myloop.golf** (and `www`) at this Worker in the Cloudflare dashboard (Custom Domains on the `myloop-golf` worker), or set a CNAME once the Worker is live.

## What this page covers (product-true)

- **Course App** — GPS yardages, plays-like, rings, flyovers, breaks, personal scorecard, save to phone
- **Outing App** — event GPS, one scorekeeper per group, hole sponsors, silent-auction browse
- **Clubs live today** — OU Golf & Learning Center, The Wyndgate, Indianwood

No fake network stats or invented testimonials.
