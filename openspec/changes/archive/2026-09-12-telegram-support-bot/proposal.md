## Why

Automating customer support through Telegram reduces agent workload and improves response times, while ensuring that unanswered or unresolved questions are gracefully escalated to human support agents. By establishing a continuous feedback loop where support agent resolutions are automatically ingested back into the knowledge base, the system progressively expands its self-service resolution rate over time.

## What Changes

- Implement a Telegram Bot interface for end-users to submit questions, view automated responses, and confirm resolution status ("Problème résolu ? OUI / NON") via interactive buttons.
- Implement a Backend API (FastAPI) orchestrating query processing, search, ticketing, and administrative actions.
- Implement a Knowledge Base system using SQLite and vector embeddings (ChromaDB / lightweight embeddings) to index FAQs, documentation, and historical solutions.
- Implement an optional/pluggable AI module (LLM generation) that can formulate answers based on knowledge base context, while allowing the system to operate in direct search retrieval mode when AI is disabled.
- Implement a Support Ticket Escalation workflow that routes unresolved inquiries to a designated Telegram Support Group when the user selects "NON".
- Implement a Support Resolution Feedback Loop allowing support agents to reply directly to tickets with new solutions, which are delivered to the user and automatically indexed into the Knowledge Base.

## Capabilities

### New Capabilities
- `telegram-bot`: Telegram bot handling end-user messaging, inline resolution confirmation buttons ("OUI / NON"), and support group ticketing interactions.
- `knowledge-base`: Storage, retrieval (lexical/semantic), and continuous updating of solutions and FAQ items.
- `ticket-escalation`: Management of support tickets, state tracking (Open, In Progress, Resolved), and routing between users and the support team.
- `ai-assistant`: Optional LLM-based answer generation and query refinement using knowledge base context.

### Modified Capabilities
None. (This is a greenfield implementation).

## Impact

- **New Backend Service**: FastAPI application providing REST endpoints for queries, knowledge base management, and ticket lifecycle.
- **Telegram Integration**: Bot service using `aiogram` / `python-telegram-bot` connected via Telegram Bot API tokens.
- **Data Persistence**: SQLite database for ticket tracking and structured knowledge entries; ChromaDB/vector store for semantic search.
- **Configuration & Environment**: New environment configuration (`.env.example`) for Telegram Bot token, Support Group ID, optional AI API keys, and database settings.
