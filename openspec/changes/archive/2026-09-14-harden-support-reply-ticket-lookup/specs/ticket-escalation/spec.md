## MODIFIED Requirements

### Requirement: Ticket creation on unresolved queries
The system SHALL create a unique support ticket whenever a user indicates their problem was not resolved or when no automated answer could be determined, and dispatch notifications to both Telegram and Email channels. When the ticket is posted as a card message to the Telegram Support Group, the system SHALL record the identity of that posted message against the ticket, so a later reply to it can be matched independently of the card's text content.

#### Scenario: User selects NON on resolution prompt
- **WHEN** the user selects "NON" on the problem resolved prompt
- **THEN** the system generates a ticket in status `OPEN`, recording the user's Telegram ID, inquiry, response history, and dispatches multi-channel alerts to the Telegram Support Group and Support Email

#### Scenario: Support group card identity recorded
- **WHEN** the ticket's card message is successfully posted to the Telegram Support Group
- **THEN** the system records that message's identity against the ticket, so it can be looked up later independently of the card's text
