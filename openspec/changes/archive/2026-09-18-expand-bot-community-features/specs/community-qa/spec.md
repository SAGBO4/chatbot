## Purpose

Lets community-group members ask support questions directly in the group and get answered publicly, while keeping all ticket resolution traffic (agent replies, ticket cards, moderation logs) confined to the existing admin group, never the community group.

## ADDED Requirements

### Requirement: Group-triggered question intake
The Telegram Bot SHALL accept a support question submitted in the configured Telegram Community Group via a dedicated trigger command followed by the question text, and SHALL forward that question to the same backend query pipeline used by the private-DM flow. Messages in the community group that do not use the trigger command SHALL NOT be treated as support questions.

#### Scenario: Member asks a question in the community group
- **WHEN** a member sends the trigger command followed by a question in the configured Telegram Community Group
- **THEN** the bot submits the question to the backend query pipeline and treats it as a new support inquiry tied to that member

#### Scenario: Ordinary group chatter is ignored
- **WHEN** a member sends a plain message in the Telegram Community Group without the trigger command
- **THEN** the bot does not submit it as a query and does not reply

### Requirement: Public tagged reply with expiring resolution controls
The Telegram Bot SHALL reply to a group-triggered question in the same group thread, tagging (mentioning) the asking member in the reply, and SHALL present the same YES/NO resolution confirmation used in DM. If no resolution response is received within a configured inactivity timeout, the bot SHALL deactivate the YES/NO controls (remove or disable them) so they can no longer be used to confirm resolution or create a ticket.

#### Scenario: Bot answers and tags the asker
- **WHEN** the backend returns an answer for a group-triggered question
- **THEN** the bot posts the answer in the community group, mentioning the asking member, together with YES/NO resolution buttons

#### Scenario: Resolution buttons expire after inactivity
- **WHEN** a group-triggered answer's YES/NO buttons receive no interaction within the configured timeout
- **THEN** the bot deactivates those buttons on the original message such that a later tap no longer confirms resolution or creates a ticket

#### Scenario: Member confirms resolution before expiry
- **WHEN** the asking member taps YES before the timeout elapses
- **THEN** the bot acknowledges resolution in the community group the same way it does for the DM flow, and the buttons are removed

### Requirement: Ticket escalation stays out of the community group
When a group-triggered question is not resolved (member taps NO, or no matching knowledge base answer exists and the member chooses to escalate), the Telegram Bot SHALL create a support ticket through the existing ticket-escalation pipeline and SHALL post all ticket-related content (the ticket card, agent resolution replies, resolution confirmations) only to the configured Telegram admin/support group and/or email, never to the Telegram Community Group. The community group message SHALL only be updated with a neutral acknowledgement that a ticket was opened, without exposing ticket internals.

#### Scenario: Escalation from the community group
- **WHEN** a member taps NO on a group-triggered answer, or the bot found no automated answer and the member requests escalation
- **THEN** a ticket is created, its card is posted to the configured admin/support group (not the community group), and the community group message is updated only with a neutral "ticket opened" acknowledgement

#### Scenario: Agent resolution never reaches the community group
- **WHEN** a support agent resolves a ticket that originated from the community group, whether via the admin group reply flow or via email
- **THEN** the resolution notification is delivered to the ticket's originating user and to the admin group as usual, and no message about it is posted to the Telegram Community Group

### Requirement: Community-scoped message cleanup
The Telegram Bot SHALL provide a `/purge` command usable only by administrators of the Telegram Community Group (verified via the Telegram Bot API) that deletes a bounded number of recent bot-authored or flagged messages in that group, so an admin can remove an overly long or unwanted bot reply from the community group without needing admin group access.

#### Scenario: Admin purges recent bot messages
- **WHEN** a verified admin of the Telegram Community Group issues `/purge` with a valid count in that group
- **THEN** the bot deletes that number of its own most recent messages in the group and confirms the deletion count to the admin

#### Scenario: Non-admin cannot purge
- **WHEN** a member who is not an admin of the Telegram Community Group issues `/purge`
- **THEN** the bot refuses the action and does not delete any message
