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

### Requirement: Ticket user ownership access control
The system SHALL validate user identity and access boundaries when ticket details or ticket lists are requested on behalf of an end-user, preventing unauthorized cross-user data access (IDOR).

#### Scenario: User queries their own tickets
- **WHEN** a client requests tickets specifying a `user_id` matching the authenticated user context
- **THEN** the system returns only tickets belonging to that `user_id`

#### Scenario: User attempts to access another user's ticket
- **WHEN** a user-scoped client attempts to retrieve a ticket ID belonging to a different user
- **THEN** the system rejects the request with an HTTP 403 Forbidden or 404 Not Found error

#### Scenario: Trusted bot service queries tickets
- **WHEN** a service request is authenticated with the master `API_KEY` without end-user constraints
- **THEN** the system allows service-level ticket operations required for administrative escalation and bot management

### Requirement: Resilient ticket escalation background dispatch
The system SHALL execute background multi-channel alert notifications (support group card and email dispatch) in isolated execution contexts such that failures in external relay networks do not compromise ticket persistence or abort the response.

#### Scenario: Telegram relay failure during ticket creation
- **WHEN** a ticket is escalated and the Telegram bot API is temporarily unreachable
- **THEN** the error is logged, the ticket remains safely created in status `OPEN`, and the client receives an HTTP 201 response
