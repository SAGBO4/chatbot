# community-moderation Specification

## Purpose
Gives Telegram-verified admins of the community group baseline moderation tools (mute, ban, kick, warn) to manage members without leaving Telegram or relying on a separate bot.

## Requirements

### Requirement: Admin-only moderation commands
The Telegram Bot SHALL provide `/mute`, `/unmute`, `/ban`, `/kick`, and `/warn` commands usable only inside the configured Telegram Community Group, targeting a member either by replying to their message or by explicit user reference. Each command SHALL be rejected with no effect on the target member unless the invoking user is verified, via the Telegram Bot API, to currently hold an admin (or owner) role in that group.

#### Scenario: Admin mutes a member
- **WHEN** a verified admin of the Telegram Community Group issues `/mute` targeting a member (by reply or reference), optionally with a duration
- **THEN** the bot restricts that member's ability to send messages in the group for the given duration (or indefinitely if none is given) and confirms the action in the group

#### Scenario: Admin unmutes a member
- **WHEN** a verified admin issues `/unmute` targeting a previously muted member
- **THEN** the bot restores that member's ability to send messages in the group and confirms the action

#### Scenario: Admin bans a member
- **WHEN** a verified admin issues `/ban` targeting a member
- **THEN** the bot removes that member from the group and prevents them from rejoining until unbanned, and confirms the action

#### Scenario: Admin kicks a member
- **WHEN** a verified admin issues `/kick` targeting a member
- **THEN** the bot removes that member from the group while still allowing them to rejoin, and confirms the action

#### Scenario: Admin warns a member
- **WHEN** a verified admin issues `/warn` targeting a member, optionally with a reason
- **THEN** the bot records the warning against that member and confirms the action in the group, without restricting the member's ability to send messages

#### Scenario: Non-admin invokes a moderation command
- **WHEN** a member who is not a verified admin of the Telegram Community Group issues any of `/mute`, `/unmute`, `/ban`, `/kick`, or `/warn`
- **THEN** the bot refuses the command, takes no action against any member, and does not reveal any member's warning history

### Requirement: Moderation actions confined to the community group
The system SHALL apply moderation actions only within the Telegram Community Group they were issued in and SHALL NOT allow a moderation command issued in any other chat (including the admin group or a private DM) to affect community group membership or permissions.

#### Scenario: Moderation command issued outside the community group
- **WHEN** a `/mute`, `/unmute`, `/ban`, `/kick`, or `/warn` command is sent in a chat other than the configured Telegram Community Group
- **THEN** the bot does not apply any moderation action to any member
