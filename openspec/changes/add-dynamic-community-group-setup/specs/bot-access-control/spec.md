## Purpose

Establishes a small, trusted access-control layer - a single env-defined bot owner plus an owner-managed whitelist - that gates who may configure the bot (community group, language), without introducing a new source of trust beyond what the deployment operator already controls via `.env`.

## ADDED Requirements

### Requirement: Env-defined bot owner
The system SHALL recognize the Telegram user id configured as `BOT_OWNER_TELEGRAM_ID` (an environment variable, set by the deployment operator) as the bot owner. The owner SHALL always be authorized to configure the community group, manage the admin whitelist, and change the bot language, regardless of their role in any Telegram group.

#### Scenario: Owner is always authorized
- **WHEN** the Telegram user whose id matches `BOT_OWNER_TELEGRAM_ID` invokes a configuration command
- **THEN** the bot treats them as authorized without consulting the whitelist

#### Scenario: Owner not configured
- **WHEN** `BOT_OWNER_TELEGRAM_ID` is unset or empty
- **THEN** no user is granted owner authorization, and configuration commands are refused for everyone until an owner is configured

### Requirement: Owner-managed admin whitelist
The system SHALL provide a `/whitelist add <user_id>` and `/whitelist remove <user_id>` command, usable only by the bot owner, that grants or revokes another Telegram user's authorization to configure the community group and the bot language. A whitelisted admin SHALL NOT be able to add or remove other whitelist entries.

#### Scenario: Owner whitelists a new admin
- **WHEN** the bot owner runs `/whitelist add <user_id>`
- **THEN** that user becomes authorized to run community-group-setup and bot-localization configuration commands

#### Scenario: Owner revokes an admin
- **WHEN** the bot owner runs `/whitelist remove <user_id>`
- **THEN** that user immediately loses authorization to run those configuration commands

#### Scenario: Whitelisted admin cannot manage the whitelist
- **WHEN** a whitelisted (non-owner) admin runs `/whitelist add` or `/whitelist remove`
- **THEN** the bot refuses the command and the whitelist is unchanged

#### Scenario: Non-owner, non-whitelisted user is rejected
- **WHEN** a Telegram user who is neither the owner nor on the whitelist attempts to run `/whitelist`, the community-group-setup command, or the language command
- **THEN** the bot refuses the command and takes no configuration action
