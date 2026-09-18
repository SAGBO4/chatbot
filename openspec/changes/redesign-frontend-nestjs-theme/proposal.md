## Why

The frontend interface requires a complete visual overhaul inspired by the modern, developer-centric aesthetic of NestJS (signature crimson `#ea2845` gradients, deep onyx backgrounds `#0b0e14`, glassmorphism, terminal aesthetics, and crisp typography). In addition, the interface must provide full coverage of all FastAPI backend capabilities (support queries, ticket lifecycle and agent resolution, knowledge base ingestion and statistics, live crypto market prices, community moderation warnings, and bot dynamic settings) and feature an interactive French/English (`FR`/`EN`) language switcher in the primary menu matching the bot's bilingual nature.

## What Changes

- **NestJS Graphic Identity**:
  - Reconfigure theme tokens with NestJS colors: signature crimson `#ea2845`, ruby glow `#ff318c`, deep dark backgrounds (`#0b0e14`, `#11141c`), surface cards (`#171b24`), and glowing hover borders (`#ea2845`/40).
  - Modern NestJS-style layout: glassmorphism header, hero with crimson gradient accents, code-card styling, badge pills, and tabbed developer dashboard.
- **Bilingual Interface (FR / EN)**:
  - Add an interactive language toggle button (`FR` | `EN`) in the top navigation bar.
  - Implement a lightweight client-side i18n context providing complete French and English translations for all pages, search prompts, ticket statuses, and buttons, persisted in local state.
- **Comprehensive Backend Integration**:
  - **Support & AI Query** (`/api/query`, `/health`): Natural language search with confidence scoring, KB article source badges, and YES/NO resolution confirmation.
  - **Tickets Management** (`/api/tickets`): User escalation submission, ticket list with status filters, and ticket resolution action (`POST /api/tickets/{id}/resolve`).
  - **Knowledge Base Explorer & Ingestion** (`/api/knowledge`): Article directory, creation form (`/api/knowledge/ingest`), and database metrics (`/api/knowledge/stats`).
  - **Crypto Market Dashboard** (`/api/crypto`): Real-time price cards, 24h changes, market cap, and volume for tracked assets (BTC, ETH, FIRO, etc.).
  - **Community Moderation** (`/api/moderation`): User warning lookup and moderation log viewer.
  - **Bot Settings & Whitelist** (`/api/settings`): Community group ID viewer, active language setting, and admin whitelist verification checker.

## Capabilities

### New Capabilities
- `web-frontend`: Complete Next.js frontend application redesigned with the NestJS visual charter, featuring a bilingual menu toggle (FR/EN) and full interface coverage for all backend support, knowledge base, crypto, and administration endpoints.

### Modified Capabilities
<!-- None: All FastAPI endpoints and bot operations remain unchanged. -->

## Impact

- **Frontend Codebase (`frontend/`)**:
  - CSS / Tailwind configuration updated with NestJS color tokens and gradients.
  - New i18n module (`frontend/src/lib/i18n/`) with translations and language context.
  - Enhanced API client (`frontend/src/lib/api.ts`) covering knowledge articles, crypto prices, moderation warnings, and settings endpoints.
  - New and updated pages/views: Knowledge explorer (`/knowledge`), Crypto dashboard (`/crypto`), Admin/Settings (`/settings`), redesigned Home (`/`) and Tickets (`/tickets`).
- **Dependencies**: No external runtime additions required; uses React Context, Tailwind CSS, and Next.js App Router.
