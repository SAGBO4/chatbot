## ADDED Requirements

### Requirement: User query rate limiting and flood protection
The Telegram Bot and backend API SHALL throttle incoming user messages and queries to prevent denial-of-service, abuse, and excessive LLM API quota consumption. The system SHALL enforce per-user rate limits on the bot interface and rate limits on backend query endpoints.

#### Scenario: User sends queries within allowed rate limit
- **WHEN** a user submits queries within the configured rate threshold (e.g. at most 5 requests per 10 seconds)
- **THEN** the bot processes each query normally and returns responses

#### Scenario: User exceeds message rate threshold
- **WHEN** a user sends queries exceeding the rate threshold in a short window
- **THEN** the bot rejects the excess messages with a friendly throttling notification ("Veuillez patienter quelques secondes avant d'envoyer un nouveau message") and suppresses backend API calls
