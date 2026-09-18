## Context

The repository contains a FastAPI backend (`backend/`) and Telegram bot (`bot/`) providing automated customer support, knowledge base indexing, and ticket escalation. All backend REST APIs (`/health`, `/api/query`, `/api/tickets`) are operational and protected by configurable API keys with existing CORS support.

Currently, no web frontend exists. This design establishes a Next.js application in `frontend/` styled after the official Stack Wallet graphic charter (open-source cryptocurrency wallet by Cypher Stack). See [proposal.md](proposal.md) for background and motivation.

## Goals / Non-Goals

**Goals:**
- Initialize a standalone Next.js (App Router, TypeScript, Tailwind CSS) project inside `frontend/`.
- Establish the Stack Wallet design system token definitions (dark theme background `#232323`, elevated card surfaces `#2E2E32`, Stack blue `#3030D0` / `#5959D9`, crypto accents, custom shadows, and typography).
- Build reusable UI components adhering to Stack Wallet branding:
  - Header with branding, navigation links, and live backend connection badge.
  - Interactive Knowledge Base & Support Search card with resolution feedback buttons (YES / NO).
  - Ticket escalation dialog and user ticket tracking view.
- Provide a clean API client layer (`frontend/src/lib/api.ts`) managing backend communication, error handling, and API key forwarding.
- Configure local developer experience (`package.json` scripts, `tsconfig.json`, `.env.example`, `next.config.js`).

**Non-Goals:**
- Rewriting backend API routes or modifying the Telegram bot architecture.
- Implementing complex multi-role JWT authentication in this initial setup (standard API key / user token header is used).
- Full crypto wallet key management or blockchain node synchronization (the frontend serves as the support/chatbot portal for Stack Wallet).

## Decisions

### Decision 1: Next.js with App Router and TypeScript
- **Rationale**: Next.js App Router provides modern server/client component boundaries, zero-config bundling, fast developer iteration, and straightforward static/hybrid deployment. TypeScript ensures type safety with backend schemas.
- **Alternatives considered**:
  - *Vite + React SPA*: Lightweight, but lacks built-in server-side API proxying, SEO defaults, and unified fullstack deployment options.
  - *Plain HTML/JS*: Faster to prototype, but difficult to maintain, scale, and align with modern design systems.

### Decision 2: Tailwind CSS with Extended Stack Wallet Palette
- **Rationale**: Configuring custom theme tokens in `tailwind.config.js` allows declarative, consistent usage of Stack Wallet's visual language across all components without CSS bloat.
  - Backgrounds: `stack-dark` (`#232323`), `stack-surface` (`#2A2B2E`), `stack-card` (`#323338`)
  - Accents: `stack-blue` (`#3030D0`), `stack-blue-hover` (`#5959D9`), `stack-cyan` (`#41C7F2`)
  - Semantic: `stack-success` (`#32A072`), `stack-warning` (`#FAA51A`), `stack-error` (`#EF4049`)
- **Alternatives considered**:
  - *Raw CSS files*: Harder to maintain consistency across components and slower to build responsive layouts.
  - *Component libraries (e.g. MUI)*: Brings heavy opinionated styling that conflicts with Stack Wallet's custom minimalist crypto aesthetic.

### Decision 3: Modular Client Architecture
- **Directory Layout**:
  ```
  frontend/
  ├── src/
  │   ├── app/
  │   │   ├── layout.tsx         # Root layout with Stack Wallet shell and fonts
  │   │   ├── page.tsx           # Main support portal & FAQ search interface
  │   │   ├── tickets/
  │   │   │   └── page.tsx       # Ticket tracking and escalation overview
  │   │   └── globals.css        # Global CSS & Tailwind imports
  │   ├── components/
  │   │   ├── layout/            # Header, Footer, Navigation
  │   │   ├── support/           # SearchBar, AnswerCard, FeedbackButtons
  │   │   ├── tickets/           # TicketForm, TicketList, StatusBadge
  │   │   └── ui/                # Button, Card, Input, Modal
  │   ├── lib/
  │   │   └── api.ts             # Typed backend API client
  │   └── types/
  │       └── index.ts           # Shared TypeScript interfaces (Ticket, QueryResponse, etc.)
  ├── public/                    # Assets and branding logos
  ├── package.json
  ├── tsconfig.json
  ├── tailwind.config.ts
  └── .env.example
  ```

### Decision 4: Centralized API Client with Environment Fallbacks
- **Rationale**: `frontend/src/lib/api.ts` abstracts communication to `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), automatically attaching `X-API-Key` headers when provided and transforming network exceptions into typed error objects.

## Risks / Trade-offs

- **[Risk] Cross-Origin Resource Sharing (CORS) during local development**
  - *Mitigation*: The backend already configures `CORSMiddleware` with `CORS_ALLOWED_ORIGINS` (defaults to `*`). Frontend defaults to calling `http://localhost:8000` directly or can proxy requests via Next.js Route Handlers if needed.
- **[Risk] Node.js version discrepancies on host system**
  - *Mitigation*: Document engine requirements (Node.js >= 18.18.0) and include a `.nvmrc` or standard `package.json` `engines` declaration.
- **[Risk] Exposing secret API keys in client-side bundles**
  - *Mitigation*: Public support queries use public access or Next.js route proxying; administrative ticket features warn against hardcoding secrets into `NEXT_PUBLIC_` variables.

## Migration / Deployment Plan

1. **Local Setup**: Run `cd frontend && npm install && npm run dev` to start frontend on `http://localhost:3000`.
2. **Backend Connection**: Verify `backend/` is running on port 8000; the frontend header status pill will indicate live connectivity via `/health`.
3. **Rollback Strategy**: The frontend is contained entirely in `frontend/`, meaning existing backend and Telegram bot services remain completely decoupled and operational if frontend setup is paused or reverted.
