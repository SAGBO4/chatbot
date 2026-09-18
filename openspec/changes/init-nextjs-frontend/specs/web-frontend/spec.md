## Purpose

Provides a modern, responsive web application for interacting with the chatbot knowledge base and support ticket system, adhering to the official Stack Wallet visual identity and design system.

## ADDED Requirements

### Requirement: Stack Wallet Visual Design System and Theming
The web frontend SHALL implement the official Stack Wallet design system across all pages and reusable components, incorporating dark charcoal foundation backgrounds (`#232323`), elevated card surfaces, Stack blue brand accents (`#3030D0`, `#5959D9`), semantic status colors (success `#32A072`, warning `#FAA51A`, error `#EF4049`), and crisp sans-serif typography.

#### Scenario: Rendering default themed layout
- **WHEN** a user visits any page of the web application
- **THEN** the page renders using the Stack Wallet color palette with appropriate contrast ratios, card styling, and brand accents

#### Scenario: Visual feedback on interactive states
- **WHEN** a user hovers over, focuses, or activates buttons, inputs, or navigation links
- **THEN** interactive elements display states utilizing Stack Wallet highlight colors and smooth transitions

### Requirement: Interactive Knowledge Base Search and Support Portal
The web frontend SHALL provide a user-facing query portal that submits user questions to the backend API (`/api/query`) and displays answered solutions with confidence scores, source references, and resolution confirmation options.

#### Scenario: Submitting a valid support query
- **WHEN** a user enters a question into the support search box and submits it
- **THEN** the application queries the backend API and renders the retrieved solution card with answer text, source, and a prompt asking if the issue was resolved

#### Scenario: Backend unreachable or query failure
- **WHEN** the backend query request times out or returns an HTTP error code
- **THEN** the application displays a user-friendly error notification in accordance with Stack Wallet error styling and prompts to retry or submit a ticket

### Requirement: Ticket Creation and Status Tracking
The web frontend SHALL allow users to escalate an unresolved issue into a support ticket via the backend API (`/api/tickets`) and view ticket history and resolution status.

#### Scenario: Submitting an escalation ticket
- **WHEN** a user indicates that an answer did not resolve their issue or manually chooses to open a ticket
- **THEN** the frontend prompts for user/contact details and subject, submits the ticket to `/api/tickets`, and displays the created ticket ID with confirmation

#### Scenario: Viewing ticket status
- **WHEN** a user requests status for an existing ticket ID or user ID
- **THEN** the application fetches ticket records and renders status badges (Open, Pending, Resolved, Closed) matching the design system colors

### Requirement: Responsive Layout and Component Architecture
The web application SHALL deliver a responsive interface organized with a top navigation bar displaying Stack Wallet branding, a primary content container, and a footer displaying API connectivity status.

#### Scenario: Rendering on mobile viewports
- **WHEN** a user loads the application on a mobile screen width
- **THEN** layout elements collapse into a single-column view with a responsive navigation drawer or compact menu without horizontal overflow

#### Scenario: Displaying backend service health
- **WHEN** the frontend loads
- **THEN** it checks the backend `/health` endpoint and renders an active status indicator (online/degraded/offline) in the footer or header
