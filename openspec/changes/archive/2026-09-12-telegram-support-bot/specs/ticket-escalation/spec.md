## Purpose

Tracks support ticket lifecycles, persists user context and question history, coordinates ticket escalation to support agents, and records verified resolutions.

## ADDED Requirements

### Requirement: Ticket creation on unresolved queries
The system SHALL create a unique support ticket whenever a user indicates their problem was not resolved or when no automated answer could be determined.

#### Scenario: User selects NON on resolution prompt
- **WHEN** the user selects "NON" on the problem resolved prompt
- **THEN** the system generates a ticket in status `OPEN`, recording the user's Telegram ID, the inquiry, automated response history, and timestamp

### Requirement: Ticket status transitions
The system SHALL manage ticket states through `OPEN`, `IN_PROGRESS`, and `RESOLVED`.

#### Scenario: Agent begins working on ticket
- **WHEN** an agent interacts with or claims a ticket
- **THEN** the ticket status updates to `IN_PROGRESS`

#### Scenario: Agent submits solution
- **WHEN** an agent provides a solution to an open or in-progress ticket
- **THEN** the ticket status transitions to `RESOLVED`, storing the agent identifier, resolution text, and completion timestamp

### Requirement: Triggering knowledge base ingestion upon ticket resolution
The system SHALL forward the resolved ticket's original question and agent-provided solution to the Knowledge Base system.

#### Scenario: Automated knowledge update trigger
- **WHEN** a ticket is transitioned to `RESOLVED` with a verified solution
- **THEN** the system triggers ingestion of the question and solution into the knowledge base
