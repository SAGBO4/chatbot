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
The Telegram Bot SHALL post escalated support tickets to the designated Telegram Support Group and capture replies from support agents.

#### Scenario: Escalated ticket posted to support group
- **WHEN** a ticket is created after a user clicks "NON"
- **THEN** the bot sends a message in the support group containing the ticket ID, user question, previous automated answer, and user Telegram handle

#### Scenario: Support agent replies to ticket
- **WHEN** a support agent replies directly to the ticket message in the support group with a solution
- **THEN** the bot transmits the agent's solution back to the original user and invokes the knowledge base update endpoint
