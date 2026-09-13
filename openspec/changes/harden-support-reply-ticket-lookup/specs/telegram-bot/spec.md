## MODIFIED Requirements

### Requirement: Support group ticket notification and reply
The Telegram Bot SHALL post escalated support tickets to the designated Telegram Support Group and capture replies from support agents. The bot SHALL only treat a reply as an agent resolution when the reply is sent in the chat configured as the Telegram Support Group; replies received in any other chat (including private messages to the bot) SHALL be ignored and produce no ticket resolution, no message delivery to the ticket's user, and no knowledge base update. Within the support group, the bot SHALL identify which ticket a reply resolves primarily by the identity of the replied-to message (its Telegram message id, as recorded when the ticket card was posted), falling back to parsing the card's text only when no ticket is found for that message id.

#### Scenario: Escalated ticket posted to support group
- **WHEN** a ticket is created after a user clicks "NON"
- **THEN** the bot sends a message in the support group containing the ticket ID, user question, previous automated answer, and user Telegram handle, and the identity of that posted message is recorded against the ticket

#### Scenario: Support agent replies to ticket
- **WHEN** a support agent replies directly to the ticket message in the support group with a solution
- **THEN** the bot resolves the ticket associated with the replied-to message's identity, transmits the agent's solution back to the original user, and invokes the knowledge base update endpoint

#### Scenario: Reply matched via fallback text parsing
- **WHEN** a support agent replies in the support group to a message whose identity is not linked to any ticket, but whose text still matches the ticket card pattern (ticket ID and user ID markers)
- **THEN** the bot resolves the ticket identified by that text match, exactly as it would via the primary lookup

#### Scenario: Reply that cannot be matched to any ticket
- **WHEN** a support agent replies in the support group to a message that is neither linked to a ticket by identity nor matches the ticket card text pattern
- **THEN** the bot takes no resolution action and replies in the group explaining that the message could not be matched to a ticket

#### Scenario: Reply received outside the support group is ignored
- **WHEN** a message reproducing the ticket card pattern (ticket ID and user ID markers) is replied to in a chat that is not the configured Telegram Support Group, such as a private conversation with the bot
- **THEN** the bot takes no action: it does not resolve the ticket, does not send any message to the referenced user, and does not update the knowledge base
