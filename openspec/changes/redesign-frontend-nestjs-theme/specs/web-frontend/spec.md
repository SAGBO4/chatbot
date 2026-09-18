## Purpose

Provides a high-performance, developer-focused web portal adopting the NestJS visual design charter, equipped with a top-menu bilingual switcher (FR/EN) and interfaces for 100% of backend capabilities including support search, ticket escalation & resolution, knowledge base management, live crypto market tracking, moderation warnings, and bot dynamic settings.

## ADDED Requirements

### Requirement: NestJS Visual Design System and Aesthetic
The web application SHALL implement the official NestJS design aesthetic, utilizing deep dark foundations (`#0b0e14`, `#11141c`), surface cards (`#171b24`, `#1e2330`), signature crimson and ruby gradient accents (`#ea2845`, `#ff318c`, `#c0138a`), glassmorphic header blur, code-styled surfaces, and crisp sans-serif typography.

#### Scenario: Rendering default NestJS theme
- **WHEN** a user visits any route of the frontend application
- **THEN** pages display with NestJS dark backgrounds, crimson brand accents, ruby card border highlights, and clear visual hierarchy

#### Scenario: Hover and interaction feedback
- **WHEN** a user hovers over action buttons, navigation tabs, or feature cards
- **THEN** elements display crimson glow transitions, active indicators, and elevated focus states

### Requirement: Bilingual Interface and Language Switcher (FR / EN)
The web application SHALL include a language selector (`FR` | `EN`) in the primary navigation bar allowing users to switch between French and English, instantaneously updating all navigation links, search placeholders, card content, form labels, and status badges.

#### Scenario: Switching language between French and English
- **WHEN** a user clicks the language toggle button in the header
- **THEN** the active locale toggles between French and English and all UI labels update immediately without requiring a full page reload

#### Scenario: Persisting language selection
- **WHEN** a user selects a preferred language and navigates to another page or refreshes the browser
- **THEN** the application restores the user's previously selected language preference

### Requirement: Full Backend Capabilities Coverage
The web application SHALL provide dedicated, interactive interfaces connecting to all backend FastAPI routes, including support query (`/api/query`), ticket management and resolution (`/api/tickets`, `/api/tickets/{id}/resolve`), knowledge base exploration and ingestion (`/api/knowledge`), live crypto market data (`/api/crypto`), moderation warnings (`/api/moderation`), and bot settings (`/api/settings`).

#### Scenario: Submitting support queries and validating resolution
- **WHEN** a user submits a natural language question on the home search portal
- **THEN** the application queries `/api/query`, renders the matched answer with confidence percentage and article reference, and offers YES/NO resolution confirmation

#### Scenario: Escalating and resolving support tickets
- **WHEN** an issue requires team intervention
- **THEN** a user can open a ticket via `/api/tickets`, filter tickets by ID or user ID, and authorized agents can resolve tickets directly via `/api/tickets/{id}/resolve`

#### Scenario: Browsing and ingesting knowledge base articles
- **WHEN** visiting the Knowledge Base section
- **THEN** the application displays KB database statistics, lists existing articles with search/pagination, and allows ingesting new question-solution pairs via `/api/knowledge/ingest`

#### Scenario: Viewing live crypto prices
- **WHEN** accessing the Crypto Market section
- **THEN** the application fetches `/api/crypto/prices` and renders live prices, 24h percentage changes, market cap, and volume for all mapped cryptocurrencies

#### Scenario: Checking user moderation status and bot configuration
- **WHEN** accessing the Moderation / Settings section
- **THEN** users and administrators can query user warnings (`/api/moderation/warnings/{user_id}`), verify admin whitelist membership, and view configured community group IDs
