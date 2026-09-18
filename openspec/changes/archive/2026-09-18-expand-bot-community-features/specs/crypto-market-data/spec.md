## Purpose

Gives users and community-group members quick access to live cryptocurrency price and market statistics from within Telegram, matching the informational commands offered by common crypto community bots.

## ADDED Requirements

### Requirement: Per-asset price lookup command
The Telegram Bot SHALL support a command per recognized cryptocurrency (for example `/btc`, `/firo`) that, when invoked in a private chat or in the configured Telegram Community Group, fetches current market data for that asset from the configured market-data provider and replies with at least: current price, 24-hour percentage change, market capitalization, and 24-hour trading volume.

#### Scenario: Known asset lookup
- **WHEN** a user sends `/btc` (or another supported asset command)
- **THEN** the bot replies with that asset's current price, 24h change, market cap, and 24h volume

#### Scenario: Unrecognized asset alias
- **WHEN** a user sends an asset command that does not map to any asset known to the provider
- **THEN** the bot replies that the asset is not recognized, without crashing or leaving the command unanswered

### Requirement: Resilience to market-data provider failures
The system SHALL treat market-data provider errors (timeouts, rate limiting, malformed responses) as recoverable failures: it SHALL reply to the user with a clear "data temporarily unavailable" message and SHALL NOT let a provider failure crash the bot process or block other bot commands.

#### Scenario: Provider timeout
- **WHEN** the market-data provider does not respond within the configured timeout
- **THEN** the bot replies that price data is temporarily unavailable and remains responsive to other commands

#### Scenario: Provider rate limit reached
- **WHEN** the market-data provider returns a rate-limit error
- **THEN** the bot replies that price data is temporarily unavailable rather than surfacing a raw provider error
