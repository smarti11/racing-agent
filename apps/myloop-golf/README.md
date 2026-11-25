# MyLoop Golf — myloop.golf

Public homepage for **MyLoop Golf**: a club-branded phone experience built for the player. Marketing copy stays high-level on purpose — product details are for private walkthroughs.

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

Point **myloop.golf** (and `www`) at this Worker in the Cloudflare dashboard (Custom Domains on the `myloop-golf` worker).

## Positioning (keep public copy vague)

- Player-first, club-branded experience
- Everyday play and outing day — without listing features
- Partnerships: select / exclusive positioning (no named clubs)

No named clubs, no feature inventory, no fake network stats.
