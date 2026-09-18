## Purpose

Lets an authorized owner/admin set or change which Telegram group is the active community group at any time through a guided in-bot tutorial, instead of requiring a redeploy with a new `TELEGRAM_COMMUNITY_GROUP_ID` environment value.

## ADDED Requirements

### Requirement: Guided first-contact tutorial
When an authorized user (the bot owner or a whitelisted admin, per bot-access-control) starts a private conversation with the bot and no community group is currently configured, the bot SHALL present a short guided tutorial explaining how to configure one. A user who is not authorized, or who is authorized but a community group is already configured, SHALL NOT see this tutorial automatically.

#### Scenario: Authorized user's first contact with no community group configured
- **WHEN** the bot owner or a whitelisted admin sends `/start` in a private chat and no community group is currently configured
- **THEN** the bot replies with a tutorial explaining how to add the bot to a group and configure it as the community group

#### Scenario: Community group already configured
- **WHEN** an authorized user sends `/start` in a private chat and a community group is already configured
- **THEN** the bot shows the normal welcome message, not the setup tutorial

### Requirement: Configuring the active community group
The system SHALL provide a command, usable only by the bot owner or a whitelisted admin, that sets or replaces the currently active community group with the Telegram group the command is confirmed against. Only one community group SHALL be active at a time; configuring a new one replaces the previous one.

#### Scenario: Authorized admin configures the community group
- **WHEN** the bot owner or a whitelisted admin completes the configuration command for a Telegram group
- **THEN** that group becomes the active community group, replacing any previously configured one, and the bot confirms the change

#### Scenario: Unauthorized user cannot configure the community group
- **WHEN** a Telegram user who is neither the owner nor a whitelisted admin attempts to run the configuration command
- **THEN** the bot refuses the command and the active community group is unchanged

#### Scenario: Reconfiguration at any time
- **WHEN** an authorized user runs the configuration command again for a different group while a community group is already active
- **THEN** the previously active community group stops being treated as the community group (community-qa and community-moderation commands no longer apply there), and the newly configured group becomes active

### Requirement: Community group resolved dynamically everywhere
Every capability that scopes behavior to "the community group" (community-qa's `/ask` trigger and `/purge`, community-moderation's commands) SHALL resolve the active community group from the persisted, dynamically-configurable value at the time of each request, never from a fixed deployment-time value.

#### Scenario: Behavior follows the currently configured group
- **WHEN** the active community group is changed via the configuration command
- **THEN** community-qa and community-moderation commands immediately apply to the newly configured group and no longer apply to the previous one, without restarting the bot
