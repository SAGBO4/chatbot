## ADDED Requirements

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
