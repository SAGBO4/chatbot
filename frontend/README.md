# NestSupport Portal (Next.js Frontend - NestJS Design System)

Modern, developer-centric web frontend for the Telegram Support Bot and Knowledge Base, inspired by the official **NestJS** (`nestjs.com`) graphic identity.

---

## NestJS Design System

- **Brand Palette**:
  - Signature Crimson: `#ea2845`
  - Ruby Glow: `#ff318c` / `#c0138a`
  - Gradient Backgrounds: `linear-gradient(135deg, #ea2845 0%, #c0138a 100%)`
  - Dark Onyx Foundations: `#0b0e14`, `#07090d`, `#131722`
  - Surface Cards: `#181c28` / `#1f2536` with ruby border glows
- **Typography & Aesthetics**:
  - Clean sans-serif typography (`Manrope` / system sans)
  - Monospace code and terminal-styled outputs (`Geist Mono`)
  - Glassmorphic top navigation bar with live API status badge

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

## Getting Started

### 1. Prerequisites

- Node.js >= 18.18.0
- Backend FastAPI running on `http://localhost:8000`

### 2. Install & Run

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 3. Port Management

```bash
# Free port 3000 if occupied
npm run kill:3000

# Alternative alias
npm run stop:3000
```
