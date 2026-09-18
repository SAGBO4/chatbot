## Why

The project currently provides Telegram bot interactions and backend REST endpoints (knowledge base, ticket escalation, AI responses, crypto market data), but lacks a dedicated web interface. Creating a Next.js front-end initialized with the official Stack Wallet graphic charter will provide users and administrators with a clean, branded, and accessible web interface to query the support system, browse FAQs, and monitor tickets.

## What Changes

- Initialize a Next.js frontend project structure under `frontend/` with TypeScript, Tailwind CSS, and App Router.
- Configure the Stack Wallet design system and theme tokens:
  - Charcoal/dark mode primary backgrounds (`#232323`, `#1c1c1e`, `#121214`), light backgrounds (`#F7F7F7`, `#FFFFFF`), and surface cards (`#2E2E32` / `#FFFFFF`).
  - Primary brand accents (`#3030D0`, `#5959D9`) and semantic colors (success `#32A072`, warning `#FAA51A`, error `#EF4049`).
  - Typography rules and layout tokens modeled on Stack Wallet's minimalist, privacy-focused cryptocurrency interface.
- Implement core layout and navigational components (header/navbar with Stack Wallet styling, responsive container, footer).
- Create a branded interactive Support & FAQ query portal communicating with the existing FastAPI backend (`/api/query`, `/api/tickets`, `/health`).
- Add development scripts, environment configuration (`.env.example`, `NEXT_PUBLIC_API_URL`), and build configurations for the frontend.

## Capabilities

### New Capabilities
- `web-frontend`: Next.js web application styled with the Stack Wallet graphic charter, providing a responsive interface for user support queries, FAQ exploration, and system status monitoring.

### Modified Capabilities
<!-- None: Backend APIs and Telegram bot capabilities remain backward compatible and unaffected. -->

## Impact

- **New Directory**: `frontend/` containing package manifests, Next.js configuration, Tailwind setup, TypeScript configuration, components, and pages.
- **Dependencies**: Node.js ecosystem dependencies (Next.js, React, Tailwind CSS, Lucide icons or similar lightweight crypto/action icons).
- **Backend**: No breaking changes to FastAPI endpoints; frontend communicates via existing CORS-enabled endpoints (`/api/query`, `/api/tickets`, `/health`).
- **DevOps / Environment**: Optional Dockerfile / docker-compose integration for running the Next.js frontend alongside backend and bot services.
