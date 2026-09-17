## Purpose

Lets the bot's messages be presented in either French or English, so a community that is not French-speaking can still use the bot naturally.

## ADDED Requirements

### Requirement: Bot-wide language setting
The system SHALL support French and English as bot-authored message languages, defaulting to French to match existing behavior. The bot owner or a whitelisted admin SHALL be able to change the active language at any time via a command; the new language SHALL apply to all bot-authored messages sent after the change.

#### Scenario: Default language is French
- **WHEN** no language has ever been explicitly configured
- **THEN** the bot sends all its messages in French

#### Scenario: Authorized admin switches to English
- **WHEN** the bot owner or a whitelisted admin runs the language command to select English
- **THEN** subsequent bot-authored messages (in any chat) are sent in English

#### Scenario: Unauthorized user cannot change the language
- **WHEN** a Telegram user who is neither the owner nor a whitelisted admin attempts to run the language command
- **THEN** the bot refuses the command and the active language is unchanged

### Requirement: Full message coverage
All bot-authored user-facing text (Q&A replies, ticket/resolution confirmations, moderation command replies, crypto replies, setup tutorial, error messages) SHALL be sourced from the active language's translations, so no user-facing bot message stays hardcoded in a single language regardless of the configured setting.

#### Scenario: Moderation confirmation follows the active language
- **WHEN** the active language is English and an admin issues `/mute`
- **THEN** the bot's confirmation reply is in English

#### Scenario: Error message follows the active language
- **WHEN** the active language is English and a bot-user-facing error occurs (e.g. an unrecognized crypto asset)
- **THEN** the error message shown to the user is in English
