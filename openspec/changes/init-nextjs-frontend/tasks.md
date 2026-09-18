## 1. Project Initialization & Tooling

- [x] 1.1 Scaffold Next.js application in `frontend/` with TypeScript, Tailwind CSS, and App Router, and verify `package.json` and directory structure exist
- [x] 1.2 Configure Tailwind CSS theme tokens (`stack-dark`, `stack-card`, `stack-blue`, semantic colors) matching the Stack Wallet graphic charter, and verify `tailwind.config.ts` compiles without error
- [x] 1.3 Create TypeScript config and environment configuration (`.env.example` defining `NEXT_PUBLIC_API_URL`), verifying types compile cleanly with `npm run build` or `npx tsc --noEmit`

## 2. Shared Types & API Client

- [x] 2.1 Define TypeScript models (`QueryRequest`, `QueryResponse`, `TicketCreate`, `TicketResponse`, `HealthResponse`) in `frontend/src/types/index.ts`, verifying type alignment with FastAPI backend schemas
- [x] 2.2 Implement backend API client in `frontend/src/lib/api.ts` with error handling for `/health`, `/api/query`, and `/api/tickets`, and verify client methods handle network failures gracefully

## 3. UI Shell & Stack Wallet Design Components

- [x] 3.1 Build Stack Wallet branded layout shell (`Header`, `Footer`, `Container`) with logo/icon, status pill, and responsive navigation drawer, verifying responsive render on desktop and mobile viewports
- [x] 3.2 Build reusable UI primitives (`Button`, `Card`, `Badge`, `Input`, `Alert`) with Stack Wallet dark theme styling and interaction states, verifying visual appearance and accessibility

## 4. Support Query & FAQ Portal

- [x] 4.1 Implement Support Search interface on the home page (`frontend/src/app/page.tsx`) allowing users to submit natural language questions, verifying submission triggers `/api/query`
- [x] 4.2 Implement Answer Card component displaying answer text, confidence rating, source attribution, and resolution feedback buttons (YES / NO), verifying visual display of results
- [x] 4.3 Implement ticket escalation trigger from negative feedback (NO) or direct button, opening the ticket creation workflow, verifying state changes

## 5. Ticket Management & Tracking Interface

- [x] 5.1 Implement ticket submission form (`TicketForm`) with validation for contact details, subject, and description, verifying submission to `/api/tickets`
- [x] 5.2 Implement ticket lookup and list page (`frontend/src/app/tickets/page.tsx`) displaying user tickets with Stack Wallet themed status badges, verifying correct status mapping

## 6. End-to-End Verification & Documentation

- [x] 6.1 Verify full frontend production build (`npm run build`) and developer dev server execution (`npm run dev`), verifying zero TypeScript or lint errors
- [x] 6.2 Update project README and add frontend documentation with setup instructions, scripts, and environment variable descriptions
