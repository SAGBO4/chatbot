<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="public/stack-logo-white.png">
    <source media="(prefers-color-scheme: light)" srcset="public/stack-logo-full.png">
    <img alt="Stack Wallet" src="public/stack-logo-full.png" width="260" valign="middle">
  </picture>
  &nbsp;&nbsp;&nbsp;
  <img src="public/stack-wallet-bot.png" width="100" alt="Stack Wallet Bot" valign="middle">
</p>

# Stack Wallet Support Portal (Telegram WebApp & Web Portal)

Mobile-first web frontend for the [Telegram Support Bot](../README.md) and Knowledge Base, styled with the official **Stack Wallet** monochrome design system and frosted glassmorphism. See the [root README](../README.md) for the product overview and [backend/README.md](../backend/README.md) for the API this frontend talks to.

---

## Stack Wallet Monochrome Glassmorphism & Mobile-First Design

- **Brand Palette & Theme**:
  - Deep Black foundations: `#000000` / `#050505`
  - Crisp White typography and icons: `#ffffff`
  - Subtle frosted translucent glass: `bg-white/[0.04]`, `backdrop-blur-2xl`
  - Translucent borders: `border-white/[0.08]` to `border-white/[0.2]`
  - Solid White primary buttons with deep black typography
- **Telegram Mini App (Web App) Optimization**:
  - Compact top header with official Stack Wallet icon and "Support" label
  - Slide-over mobile drawer navigation with background lock
  - Fixed bottom thumb-navigation dock (`BottomNav`) with safe area insets support
  - Integrated Telegram haptic feedback (`impactOccurred('light')`)
  - Input styling preventing unwanted auto-zoom on mobile browsers

---

## Bilingual Support (FR / EN)

- Built-in language toggle button (`FR` | `EN`) located in the header.
- Dynamic React `LanguageContext` translating 100% of labels, placeholders, buttons, and status tags.
- Persistent language preference saved in `localStorage`.

---

## Complete Backend Capabilities Coverage

1. **Support & Natural Language Query (`/`)**:
   - Natural language search connected to `/api/query`
   - Confidence percentage rating and KB article reference
   - Interactive two-step feedback loop (`YES / NO`) to confirm resolution or trigger escalation
2. **Support Ticket Lifecycle & Agent Resolution (`/tickets`)**:
   - User ticket submission with contact handles
   - Ticket list with user filter (`?user_id=`)
   - Direct agent ticket resolution modal (`POST /api/tickets/{id}/resolve`) with automatic knowledge base re-indexing
3. **Knowledge Base Explorer & Ingestion (`/knowledge`)**:
   - Database metrics dashboard (`/api/knowledge/stats`)
   - Article directory search and pagination (`/api/knowledge/articles`)
   - Manual knowledge ingestion modal (`POST /api/knowledge/ingest`)
4. **Live Crypto Market Data (`/crypto`)**:
   - Real-time prices, 24h change percentage, market cap, and volume (`/api/crypto/prices`)
   - Real-time search filter across tracked cryptocurrencies (BTC, ETH, FIRO, etc.)
5. **Bot Settings & Moderation (`/settings`)**:
   - Dynamic community group setup inspection (`/api/settings`)
   - Live admin whitelist verification (`/api/settings/whitelist/check/{user_id}`)
   - User moderation warnings history lookup (`/api/moderation/warnings/{user_id}`)

---

## How the frontend talks to the backend

The browser never calls the backend directly. Every request goes through a same-origin proxy (`src/app/api/backend/[...path]/route.ts`), so the backend `API_KEY` only ever exists in the Next.js server process and is never shipped to visitors' browsers.

The proxy also enforces who can do what, using the signed `initData` string Telegram gives a Mini App (verified server-side with the bot token, and rejected after 24 hours):

- **Admin-only** (must be a whitelisted admin): the `admin` endpoints, knowledge ingestion, moderation warnings, and resolving tickets.
- **Everyone else** only sees and creates their own tickets: the verified Telegram user id always overrides any id sent by the client.
- **Local development:** under `npm run dev`, requests without a Telegram session are let through so the app can be tried outside Telegram. A production build (`npm run build` + `npm start`) always enforces the verification, with no bypass.

---

## Getting Started

### 1. Prerequisites

- Node.js >= 18.18.0
- Backend FastAPI running on `http://localhost:8000`, with `API_KEY` set (see [backend/README.md](../backend/README.md))

### 2. Configure the environment

```bash
cd frontend
cp .env.example .env.local
```

These variables are read by the Next.js **server** only, never by the browser:

| Variable | Purpose |
|---|---|
| `BACKEND_API_URL` | Where the FastAPI backend is reachable from the Next.js server (defaults to `http://127.0.0.1:8000`). |
| `BACKEND_API_KEY` | Must equal the backend's `API_KEY`; the proxy sends it as the `X-API-Key` header. |
| `TELEGRAM_BOT_TOKEN` | Must be the same bot token as the backend's; used to verify that Telegram really signed the Mini App session. |

### 3. Install & Run

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Port Management

```bash
# Free port 3000 if occupied
npm run kill:3000

# Alternative alias
npm run stop:3000
```
