## MODIFIED Requirements

### Requirement: Support group ticket notification and reply
The Telegram Bot SHALL post escalated support tickets to the designated Telegram Support Group and capture replies from support agents. The bot SHALL only treat a reply as an agent resolution when the reply is sent in the chat configured as the Telegram Support Group; replies received in any other chat (including private messages to the bot) SHALL be ignored and produce no ticket resolution, no message delivery to the ticket's user, and no knowledge base update.

#### Scenario: Escalated ticket posted to support group
- **WHEN** a ticket is created after a user clicks "NON"
- **THEN** the bot sends a message in the support group containing the ticket ID, user question, previous automated answer, and user Telegram handle

#### Scenario: Support agent replies to ticket
- **WHEN** a support agent replies directly to the ticket message in the support group with a solution
- **THEN** the bot transmits the agent's solution back to the original user and invokes the knowledge base update endpoint

#### Scenario: Reply received outside the support group is ignored
- **WHEN** a message reproducing the ticket card pattern (ticket ID and user ID markers) is replied to in a chat that is not the configured Telegram Support Group, such as a private conversation with the bot
- **THEN** the bot takes no action: it does not resolve the ticket, does not send any message to the referenced user, and does not update the knowledge base
