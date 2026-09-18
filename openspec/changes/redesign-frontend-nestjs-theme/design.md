## Context

The repository contains a FastAPI backend with comprehensive endpoints (`/api/query`, `/api/tickets`, `/api/knowledge`, `/api/crypto`, `/api/moderation`, `/api/settings`, `/health`) and a Next.js frontend in `frontend/`. The initial frontend prototype was scoped only to search and tickets with a neutral wallet styling.

This design overhauls the frontend to adopt the official **NestJS** website visual identity (`nestjs.com`: signature crimson `#ea2845` gradients, onyx surfaces `#0b0e14`, glassmorphism, terminal accents, and crisp typography), introduces a header bilingual switcher (`FR` | `EN`) with persistent localization, and provides full UI coverage for all backend capabilities.

## Goals / Non-Goals

**Goals:**
- **NestJS Design System**: Rebrand the entire frontend with NestJS color tokens:
  - Backgrounds: `nest-dark` (`#0b0e14`), `nest-darker` (`#07090d`), `nest-surface` (`#171b24`), `nest-card` (`#1c212c`)
  - Crimson Accents: `nest-red` (`#ea2845`), `nest-red-hover` (`#ff3355`), `nest-ruby` (`#c0138a`), `nest-gradient` (`linear-gradient(135deg, #ea2845 0%, #c0138a 100%)`)
  - Glowing borders, badge pills, glassmorphism headers, and terminal-inspired UI components.
- **Bilingual Interface (FR / EN)**:
  - Interactive language switcher toggle in the navigation header.
  - React `LanguageProvider` and `useTranslation()` hook supplying complete translations for French and English with `localStorage` persistence.
- **Complete Backend Feature Coverage**:
  - Knowledge Base Explorer (`/knowledge`): Real-time stats (`/api/knowledge/stats`), article directory search/pagination (`/api/knowledge/articles`), and article ingestion form (`/api/knowledge/ingest`).
  - Crypto Market Dashboard (`/crypto`): Real-time price grid with 24h performance metrics (`/api/crypto/prices`).
  - Ticket Resolution (`/tickets`): User lookup plus agent action to resolve tickets (`/api/tickets/{id}/resolve`) with automatic KB ingestion toggle.
  - Settings & Moderation (`/settings`): Community group ID, active language status, admin whitelist verification (`/api/settings/whitelist/check/{user_id}`), and user moderation warnings (`/api/moderation/warnings/{user_id}`).

**Non-Goals:**
- Modifying backend schemas or changing FastAPI REST API contracts.
- Altering Telegram bot polling loops or backend database tables.

## Decisions

### Decision 1: NestJS Theming via Tailwind CSS Variables & Utilities
- **Rationale**: Defining NestJS design tokens in `globals.css` with Tailwind v4 `@theme` ensures consistent usage of `#ea2845`, gradients, dark surfaces, and ruby glowing borders across all components without CSS duplication.
- **Alternatives considered**:
  - *Hardcoding colors in each component*: Leads to inconsistencies and difficult maintenance.

### Decision 2: Native React Context for Bilingual Localization (FR / EN)
- **Rationale**: A focused `LanguageContext` with typed dictionary objects (`translations.ts`) avoids bulky third-party i18n libraries, prevents SSR hydration mismatch by resolving language client-side after mount, and provides immediate reactivity across all components when the user toggles `FR` / `EN`.
- **Alternatives considered**:
  - *next-intl / react-i18next*: Adds complex routing rewrites (`/fr/...`, `/en/...`) and extra bundle overhead for a single-page application dashboard.

### Decision 3: Extended API Client Layer
- **Architecture**: `frontend/src/lib/api.ts` is expanded to cover all backend API modules:
  - `knowledge`: `getArticles()`, `getStats()`, `ingestArticle()`
  - `crypto`: `getPrices()`, `getPrice(symbol)`
  - `tickets`: `resolveTicket(id, solution, ...)`
  - `moderation`: `getWarnings(userId)`
  - `settings`: `getSettings()`, `checkWhitelist(userId)`

### Decision 4: Route and View Modularization
- `/`: Redesigned NestJS-styled Support Hero, Search, Resolution loop, and Feature highlights.
- `/tickets`: Escalation tickets, status filters, and ticket resolution dialog.
- `/knowledge`: Knowledge Base statistics cards, article search/filter, and article creation.
- `/crypto`: Live cryptocurrency price dashboard with 24h change indicators.
- `/settings`: Bot dynamic settings overview, admin whitelist checker, and moderation warnings viewer.

## Risks / Trade-offs

- **[Risk] Hydration mismatch on initial SSR render when reading language from localStorage**
  - *Mitigation*: Initialize state with default `'fr'`, synchronize with `localStorage` in a client `useEffect` on mount, avoiding any SSR divergence.
- **[Risk] Backend endpoint rate limiting during dashboard load**
  - *Mitigation*: Handle API errors gracefully in each component with user-friendly alerts and retry buttons.
