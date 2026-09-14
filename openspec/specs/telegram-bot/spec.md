# telegram-bot Specification

## Purpose
Provides the Telegram bot interface allowing users to submit support inquiries, view answers, interactively confirm resolution, and enable support agents in a designated group to manage escalated tickets.

## Requirements

### Requirement: User query submission
The Telegram Bot SHALL receive text messages from users and forward them to the backend query processing pipeline.

#### Scenario: User sends a question
- **WHEN** a user sends a text message describing their issue in Telegram
- **THEN** the bot acknowledges receipt and forwards the query to the backend for retrieval

### Requirement: Interactive resolution confirmation
The Telegram Bot SHALL present an automated response to the user along with inline buttons asking "Problème résolu ? (OUI / NON)".

#### Scenario: Displaying resolution prompt
- **WHEN** the backend returns a response for a user query
- **THEN** the bot delivers the response accompanied by inline keyboard buttons for "OUI" and "NON"

#### Scenario: User confirms resolution with OUI
- **WHEN** the user clicks "OUI"
- **THEN** the bot updates the message confirming the resolution, closes the session, and takes no further escalation action

#### Scenario: User indicates problem not resolved with NON
- **WHEN** the user clicks "NON"
- **THEN** the bot notifies the user that a support ticket has been created and escalated to the support team

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

### Requirement: User query rate limiting and flood protection
The Telegram Bot and backend API SHALL throttle incoming user messages and queries to prevent denial-of-service, abuse, and excessive LLM API quota consumption. The system SHALL enforce per-user rate limits on the bot interface and rate limits on backend query endpoints.

#### Scenario: User sends queries within allowed rate limit
- **WHEN** a user submits queries within the configured rate threshold (e.g. at most 5 requests per 10 seconds)
- **THEN** the bot processes each query normally and returns responses

#### Scenario: User exceeds message rate threshold
- **WHEN** a user sends queries exceeding the rate threshold in a short window
- **THEN** the bot rejects the excess messages with a friendly throttling notification ("Veuillez patienter quelques secondes avant d'envoyer un nouveau message") and suppresses backend API calls
