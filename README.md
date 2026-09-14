# Telegram Support Bot with Knowledge Base & AI Feedback Loop

This project implements a complete automated support system on Telegram, connected to a FastAPI backend API, an evolving knowledge base, and a configurable AI module.

---

## System Architecture

```
                    TELEGRAM
                       │
                       ▼
                ┌──────────────┐
                │ Telegram Bot │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │ Backend API  │
                └──────┬───────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       Knowledge Base     AI (Optional)
             │                   │
             └─────────┬─────────┘
                       ▼
                 User response
                       │
                Issue resolved?
                    /       \
                  YES        NO
                   │          │
                   ▼          ▼
                  END       TICKET
                              │
                              ▼
                         SUPPORT TEAM (Telegram Group)
                              │
                              ▼
                         New solution
                              │
                              ▼
                        Knowledge Base
```

### Key Features:
1. **Automated Telegram Support**: Users ask questions and receive immediate solutions.
2. **Two-step Confirmation (YES / NO)**: Interactive inline buttons below the response to confirm resolution.
3. **Automatic Escalation (NO)**: Immediate ticket creation and notification in a private Telegram support group.
4. **Resolution via Telegram Reply**: The support team simply replies to the ticket message in the group to send the solution back to the user.
5. **Continuous Learning (Feedback Loop)**: Every solution provided by a support agent is automatically indexed into the knowledge base.
6. **Pluggable AI / Zero Extra Cost**: Operates 100% autonomously without external AI using lexical/semantic similarity search, or integrates an LLM (OpenAI, Gemini, etc.) if an API key is configured.

---

## Project Structure

```
├── backend/
│   ├── config.py                 # Pydantic configuration (environment variables)
│   ├── database.py               # Asynchronous SQLAlchemy database engine (SQLite)
│   ├── models.py                 # Models (Tickets, Knowledge Base)
│   ├── schemas.py                # Pydantic schemas for requests / responses
│   ├── main.py                   # FastAPI application and REST routes
│   └── services/
│       ├── knowledge_base.py     # KB search and ingestion engine
│       ├── query_orchestrator.py # Query orchestration pipeline
│       ├── ai_assistant.py       # Optional AI module (LLM RAG)
│       └── ticket_service.py     # Ticket lifecycle management
├── bot/
│   ├── api_client.py             # Asynchronous HTTP client to the backend
│   ├── keyboards.py              # Telegram inline keyboards (YES / NO)
│   ├── main.py                   # Telegram bot entry point (aiogram 3)
│   └── handlers/
│       ├── user_handlers.py      # Handlers for private user chats
│       └── support_handlers.py   # Handlers for the support group
├── tests/                        # Unit and end-to-end (E2E) integration test suite
├── Dockerfile                    # Production Docker image
├── docker-compose.yml            # Multi-service deployment (backend + bot)
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variables example
```

---

## Installation & Quick Start

### 1. Clone and Set Up the Environment

```bash
# Clone repository
git clone <repo_url>
cd chatbot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration file
cp .env.example .env
```

### 2. Configure the `.env` File

Edit the `.env` file with your Telegram credentials:
```ini
TELEGRAM_BOT_TOKEN=123456789:
TELEGRAM_SUPPORT_GROUP_ID=
# Enable AI (Optional)
AI_ENABLED=false
AI_API_KEY=
```

> **Tip to find your `TELEGRAM_SUPPORT_GROUP_ID`:**
> 1. Create a Telegram group for your support team and add your bot.
> 2. Send a message in the group, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` to inspect the `chat.id` (negative number starting with `-100`).

### 3. Run the Services

#### Local Development Mode:
```bash
# Terminal 1: Start backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start Telegram bot
python -m bot.main
```

#### Docker Compose Mode:
```bash
docker compose up --build -d
```

---

## Testing & Verification

The automated test suite covers unit tests, database interactions, API endpoints, and the full end-to-end (E2E) scenario:

```bash
pytest -v
```
