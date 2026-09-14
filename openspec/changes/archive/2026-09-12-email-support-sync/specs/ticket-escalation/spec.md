## MODIFIED Requirements

### Requirement: Ticket creation on unresolved queries
The system SHALL create a unique support ticket whenever a user indicates their problem was not resolved or when no automated answer could be determined, and dispatch notifications to both Telegram and Email channels.

#### Scenario: User selects NON on resolution prompt
- **WHEN** the user selects "NON" on the problem resolved prompt
- **THEN** the system generates a ticket in status `OPEN`, recording the user's Telegram ID, inquiry, response history, and dispatches multi-channel alerts to the Telegram Support Group and Support Email

### Requirement: Ticket status transitions
The system SHALL manage ticket states through `OPEN`, `IN_PROGRESS`, and `RESOLVED`, recording the channel that produced the resolution.

#### Scenario: Agent begins working on ticket
- **WHEN** an agent interacts with or claims a ticket
- **THEN** the ticket status updates to `IN_PROGRESS`

#### Scenario: Agent submits solution
- **WHEN** an agent provides a solution to an open or in-progress ticket via Telegram or Email
- **THEN** the ticket status transitions to `RESOLVED`, storing the agent identifier, resolution channel, resolution text, and completion timestamp
