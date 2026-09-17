## MODIFIED Requirements

### Requirement: Group-triggered question intake
The Telegram Bot SHALL accept a support question submitted in the currently configured community group (resolved dynamically per community-group-setup, not a fixed environment value) via a dedicated trigger command followed by the question text, and SHALL forward that question to the same backend query pipeline used by the private-DM flow. Messages in the community group that do not use the trigger command SHALL NOT be treated as support questions. When no community group is currently configured, the trigger command SHALL NOT be treated as a support question in any group.

#### Scenario: Member asks a question in the community group
- **WHEN** a member sends the trigger command followed by a question in the currently configured community group
- **THEN** the bot submits the question to the backend query pipeline and treats it as a new support inquiry tied to that member

#### Scenario: Ordinary group chatter is ignored
- **WHEN** a member sends a plain message in the currently configured community group without the trigger command
- **THEN** the bot does not submit it as a query and does not reply

#### Scenario: No community group configured yet
- **WHEN** the trigger command is sent in any group while no community group is currently configured
- **THEN** the bot does not submit it as a query and does not reply

### Requirement: Community-scoped message cleanup
The Telegram Bot SHALL provide a `/purge` command usable only by administrators of the currently configured community group (verified via the Telegram Bot API) that deletes a bounded number of recent bot-authored or flagged messages in that group, so an admin can remove an overly long or unwanted bot reply from the community group without needing admin group access.

#### Scenario: Admin purges recent bot messages
- **WHEN** a verified admin of the currently configured community group issues `/purge` with a valid count in that group
- **THEN** the bot deletes that number of its own most recent messages in the group and confirms the deletion count to the admin

#### Scenario: Non-admin cannot purge
- **WHEN** a member who is not an admin of the currently configured community group issues `/purge`
- **THEN** the bot refuses the action and does not delete any message
