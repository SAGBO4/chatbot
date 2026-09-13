# ticket-escalation Specification

## Purpose
Tracks support ticket lifecycles, persists user context and question history, coordinates ticket escalation to support agents, and records verified resolutions.

## Requirements

### Requirement: Ticket creation on unresolved queries
The system SHALL create a unique support ticket whenever a user indicates their problem was not resolved or when no automated answer could be determined, and dispatch notifications to both Telegram and Email channels. When the ticket is posted as a card message to the Telegram Support Group, the system SHALL record the identity of that posted message against the ticket, so a later reply to it can be matched independently of the card's text content.

#### Scenario: User selects NON on resolution prompt
- **WHEN** the user selects "NON" on the problem resolved prompt
- **THEN** the system generates a ticket in status `OPEN`, recording the user's Telegram ID, inquiry, response history, and dispatches multi-channel alerts to the Telegram Support Group and Support Email

#### Scenario: Support group card identity recorded
- **WHEN** the ticket's card message is successfully posted to the Telegram Support Group
- **THEN** the system records that message's identity against the ticket, so it can be looked up later independently of the card's text

### Requirement: Ticket status transitions
The system SHALL manage ticket states through `OPEN`, `IN_PROGRESS`, and `RESOLVED`, recording the channel that produced the resolution.

#### Scenario: Agent begins working on ticket
- **WHEN** an agent interacts with or claims a ticket
- **THEN** the ticket status updates to `IN_PROGRESS`

#### Scenario: Agent submits solution
- **WHEN** an agent provides a solution to an open or in-progress ticket via Telegram or Email
- **THEN** the ticket status transitions to `RESOLVED`, storing the agent identifier, resolution channel, resolution text, and completion timestamp

### Requirement: Triggering knowledge base ingestion upon ticket resolution
The system SHALL forward the resolved ticket's original question and agent-provided solution to the Knowledge Base system.

#### Scenario: Automated knowledge update trigger
- **WHEN** a ticket is transitioned to `RESOLVED` with a verified solution
- **THEN** the system triggers ingestion of the question and solution into the knowledge base
