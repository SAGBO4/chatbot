## 1. NestJS Theme System & Styling

- [x] 1.1 Update `globals.css` with NestJS design tokens (crimson `#ea2845`, ruby `#ff318c`, dark `#0b0e14`, surface `#171b24`, gradient accents), verifying `npm run build` compiles styles without error
- [x] 1.2 Redesign reusable UI primitives (`Button`, `Card`, `Badge`, `Input`, `Alert`) with NestJS crimson accents and glowing borders, verifying component rendering

## 2. Bilingual Localization (FR / EN)

- [x] 2.1 Implement `LanguageContext` and translation dictionaries (`frontend/src/lib/i18n/`) for all pages and components, verifying French and English strings are defined
- [x] 2.2 Add interactive FR / EN language switcher button to the `Header` navigation, verifying language toggles instantaneously and persists in `localStorage`

## 3. Comprehensive Backend API Client Extensions

- [x] 3.1 Define TypeScript models for Knowledge, Crypto, Moderation, and Settings in `frontend/src/types/index.ts`, verifying compatibility with FastAPI schemas
- [x] 3.2 Extend `frontend/src/lib/api.ts` with methods for Knowledge Articles & Stats, Ticket Resolution, Crypto Prices, Warnings, and Whitelist checking, verifying client methods compile cleanly

## 4. Navigation & Layout Modernization

- [x] 4.1 Update `Header`, `Footer`, and layout shell with NestJS logo/mark, navigation links (Support, Tickets, Knowledge Base, Crypto, Settings), and live health indicator, verifying responsive rendering
- [x] 4.2 Redesign Home page (`frontend/src/app/page.tsx`) with NestJS crimson hero banner, interactive search, answer card with feedback buttons, and feature showcase, verifying user query submission

## 5. New Capability Pages (Knowledge, Crypto, Settings, Ticket Resolution)

- [x] 5.1 Implement Knowledge Base page (`frontend/src/app/knowledge/page.tsx`) with stats cards, article listing, and article ingestion modal, verifying `/api/knowledge` data loading
- [x] 5.2 Implement Crypto Market page (`frontend/src/app/crypto/page.tsx`) with real-time price cards, 24h change indicators, and search, verifying `/api/crypto/prices` integration
- [x] 5.3 Enhance Tickets page (`frontend/src/app/tickets/page.tsx`) with agent resolution modal (`/api/tickets/{id}/resolve`), verifying status transitions
- [x] 5.4 Implement Settings & Moderation page (`frontend/src/app/settings/page.tsx`) with community group info, language settings, whitelist lookup, and user warning query, verifying `/api/settings` and `/api/moderation` endpoints

## 6. Verification & Build

- [x] 6.1 Verify full frontend production build (`npm run build`) and linter (`npm run lint`), ensuring 0 errors
- [x] 6.2 Update frontend and project documentation with NestJS design details and bilingual navigation usage
