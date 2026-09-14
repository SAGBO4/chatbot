# ai-assistant Specification

## Purpose
Provides optional LLM-powered answer generation that synthesizes retrieved knowledge base context into clear, conversational responses for end-users.

## Requirements

### Requirement: Context-grounded response generation
When enabled, the AI Assistant SHALL use retrieved knowledge base records as grounding context to answer the user query.

#### Scenario: Successful grounded answer generation
- **WHEN** knowledge base documents are retrieved for a user query and AI generation is enabled
- **THEN** the system prompts the configured LLM provider with the documents and returns a synthesised response

#### Scenario: Insufficient context detected
- **WHEN** retrieved knowledge base documents do not contain enough information to address the query
- **THEN** the system indicates low confidence and advises escalation rather than generating unsupported claims

### Requirement: Graceful bypass when AI is disabled
The system SHALL operate seamlessly when AI generation is disabled or when API credentials are not configured.

#### Scenario: AI feature flag disabled
- **WHEN** AI generation is turned off via configuration
- **THEN** the pipeline bypasses LLM synthesis and serves direct knowledge base text matches directly to the Telegram bot

### Requirement: Resilient error handling for external LLM provider failures
The AI Assistant service SHALL gracefully handle timeouts, rate limits (HTTP 429), server errors (HTTP 5xx), and malformed responses from third-party LLM providers without raising unhandled exceptions or disrupting the query pipeline.

#### Scenario: LLM API request timeout
- **WHEN** a call to the external LLM provider encounters a network timeout or connection delay
- **THEN** the AI service logs the timeout warning and returns `None`, allowing the query pipeline to fall back directly to knowledge base match results

#### Scenario: LLM API rate limit exceeded
- **WHEN** the external LLM provider returns a 429 Rate Limit status code
- **THEN** the AI service safely catches the error, logs the rate limit event, and returns `None` without crashing

#### Scenario: LLM API server error or unexpected payload
- **WHEN** the external LLM provider responds with an HTTP 500 error or unexpected JSON schema
- **THEN** the AI service treats the response as an unavailable generation and safely falls back to standard search results
