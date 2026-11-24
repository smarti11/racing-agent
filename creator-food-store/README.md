# GoodCart — Creator Grocery Storefront Platform

A ShopMy-style creator commerce platform for **consumable grocery products** — food, beverages, supplements, produce, dairy, frozen, deli, bakery, pantry, and any single item you'd find at the grocery store.

## Features

- **Creator Storefronts** — Public `@handle` pages with curated product shelves and collections
- **Auto-Monetization** — Paste any consumable grocery product URL; platform generates affiliate tracked links
- **Affiliate Tracking** — Click logging, conversion postbacks (Amazon + Impact), attribution via sub-IDs
- **Creator Dashboard** — Analytics for clicks, conversions, earnings, and payout history
- **Stripe Connect Payouts** — Weekly creator payouts with 30-day hold period
- **Product Catalog** — Searchable grocery catalog with aisle/category filters (snacks, beverages, supplements, produce, dairy, frozen, deli, bakery, pantry)
- **Consumer Locker** — Save products, follow creators, price-drop alerts, purchase tracking
- **Browser Extension** — Chrome extension to save products while browsing retailers
- **Mobile App** — Expo React Native app (Discover, Locker, Earnings)
- **Social Auth** — Google, Instagram, TikTok OAuth + email/password
- **Compliance** — FTC affiliate disclosures, privacy policy, terms of service, admin moderation

## Tech Stack

- **Monorepo**: Turborepo + pnpm
- **Web**: Next.js 15, tRPC, NextAuth, Tailwind CSS
- **Mobile**: Expo Router + React Native
- **Extension**: Plasmo (Chrome MV3)
- **Database**: SQLite (dev) / PostgreSQL (production) via Prisma
- **Payments**: Stripe Connect

## Getting Started (dev)

```bash
cd creator-food-store
cp .env.example .env
# Edit .env — set AUTH_SECRET and DATABASE_URL (use absolute path for SQLite)

pnpm install
cd packages/db
DATABASE_URL="file:./dev.db" pnpm generate
DATABASE_URL="file:./dev.db" pnpm push
DATABASE_URL="file:./dev.db" pnpm seed
cd ../../apps/web
cp ../.env .env
# Set DATABASE_URL in apps/web/.env to absolute path, e.g.:
# DATABASE_URL="file:/full/path/to/creator-food-store/packages/db/prisma/dev.db"

pnpm dev
```

Open http://localhost:3000

### Demo Accounts (after seed)

- Creators: `/@grocerygirl`, `/@fitfuel`, `/@pantrypro`
- Seed emails: `creator@goodcart.demo`, `fitfuel@goodcart.demo`, `pantrypro@goodcart.demo`
- Consumer: `shopper@goodcart.demo`

(Password auth requires registration; seed creates users without passwords — use signup or Google OAuth.)

## Host on a Mac mini (recommended first deploy)

Same pattern as the racing-agent LaunchAgents. SQLite is fine on the Mini (always-on disk).

**Prerequisites:** Node.js 20+, internet for `pnpm install` / optional Cloudflare Tunnel.

```bash
# From your clone (example path)
cd ~/agents/racing-agent/creator-food-store

# 1) Install deps, create .env, seed DB, production build
chmod +x scripts/*.sh launchd/*.sh
./scripts/mac-mini-setup.sh

# 2) Register LaunchAgent (starts on login/reboot, KeepAlive)
./launchd/install.sh

# 3) Optional: public HTTPS URL for phone / friends
./scripts/tunnel.sh
```

| Script | Purpose |
|--------|---------|
| `scripts/mac-mini-setup.sh` | One-time (or re-run) install + build + seed |
| `scripts/run-web.sh` | Start Next.js production server (port 3000) |
| `launchd/install.sh` | Install + start `com.smarti11.goodcart.web` |
| `launchd/uninstall.sh` | Stop + remove LaunchAgent |
| `scripts/tunnel.sh` | Cloudflare quick tunnel → `*.trycloudflare.com` |

**Useful checks:**

```bash
launchctl print gui/$(id -u)/com.smarti11.goodcart.web | head
lsof -nP -iTCP:3000 -sTCP:LISTEN
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/
tail -f logs/com.smarti11.goodcart.web.out.log
```

**Local URLs:** `http://127.0.0.1:3000/` · `/discover` · `/@grocerygirl`

**Rebuild after code updates:**

```bash
git pull
./scripts/mac-mini-setup.sh   # reinstall + rebuild + reseed
./launchd/install.sh          # restart service
```

Keep the Mini awake (System Settings → Energy → prevent automatic sleeping when display is off) if you want 24/7 access.

## Project Structure

```
creator-food-store/
├── apps/
│   ├── web/          # Next.js web app + API
│   ├── mobile/       # Expo React Native app
│   └── extension/    # Chrome browser extension
└── packages/
    ├── db/           # Prisma schema + client
    ├── api/          # tRPC routers
    ├── affiliate-engine/  # URL resolve + link monetization
    └── ui/           # Shared React components
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/trpc/*` | POST | tRPC API |
| `/api/links/monetize` | POST | Monetize a product URL |
| `/go/:code` | GET | Click redirect + tracking |
| `/api/webhooks/impact` | POST | Impact conversion postback |
| `/api/webhooks/amazon` | GET | Amazon conversion postback |
| `/api/stripe/connect` | POST | Stripe Connect onboarding |
| `/api/cron/payouts` | GET | Weekly payout job |
| `/api/cron/price-alerts` | GET | Price alert checker |

## Environment Variables

See `.env.example` for all required variables. Minimum for local dev:

```
DATABASE_URL="file:./dev.db"
AUTH_SECRET="your-random-secret"
NEXT_PUBLIC_APP_URL="http://localhost:3000"
```

## Supported Retailers

Amazon, Walmart, Instacart, Kroger, Costco, Target, iHerb, Vitacost, Thrive Market, and more. Only consumable grocery products — no cookware or non-food items.

## License

Private — All rights reserved.
