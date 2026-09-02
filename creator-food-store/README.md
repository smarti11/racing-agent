# PantryLink — Creator Food Storefront Platform

A ShopMy-style creator commerce platform focused exclusively on food products. Influencers and social media users build personalized storefronts of food products they recommend and earn affiliate commission when followers purchase through their tracked links.

## Features

- **Creator Storefronts** — Public `@handle` pages with curated product shelves and collections
- **Auto-Monetization** — Paste any food product URL; platform generates affiliate tracked links
- **Affiliate Tracking** — Click logging, conversion postbacks (Amazon + Impact), attribution via sub-IDs
- **Creator Dashboard** — Analytics for clicks, conversions, earnings, and payout history
- **Stripe Connect Payouts** — Weekly creator payouts with 30-day hold period
- **Product Catalog** — Searchable food catalog with category filters
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

## Getting Started

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
# DATABASE_URL="file:/full/path/to/creator-food-store/packages/db/dev.db"

pnpm dev
```

Open http://localhost:3000

### Demo Accounts (after seed)

- Creator: `chef@pantrylink.demo` — storefront at `/@chefmaria`
- Consumer: `shopper@pantrylink.demo`

(Password auth requires registration; seed creates users without passwords — use signup or Google OAuth.)

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

Amazon, Walmart, Instacart, Thrive Market, iHerb, Vitacost, Target, Blue Apron (food-only).

## License

Private — All rights reserved.
