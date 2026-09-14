# Telegram Support Bot with Knowledge Base & AI Feedback Loop

This project implements a complete automated support system on Telegram, connected to a FastAPI Backend API, an evolving knowledge base, and a configurable AI module.

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
      Knowledge Base       AI (Optional)
             │                   │
             └─────────┬─────────┘
                       ▼
                  User Answer
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
                         New Solution
                              │
                              ▼
                        Knowledge Base
```

### Key Features:
1. **Automated Telegram Support**: Users ask questions and receive instant answers.
2. **Two-step Confirmation (YES / NO)**: Interactive buttons under each response to validate resolution.
3. **Automatic Escalation (NO)**: Immediate ticket creation and notification in a private Telegram support group.
4. **Resolution via Telegram Reply**: Support agents simply reply to the ticket card message in the group to forward the solution to the user.
5. **Continuous Learning (Feedback Loop)**: Every solution provided by a support agent is automatically indexed into the knowledge base.
6. **Pluggable AI / Zero Extra Cost**: Operates 100% autonomously without AI using lexical/semantic similarity search, or with an LLM (OpenAI, Gemini, DeepSeek) if an API key is configured.

---

## Project Structure

```
├── backend/
│   ├── config.py                 # Pydantic configuration (environment variables)
│   ├── database.py               # Asynchronous SQLAlchemy database engine (SQLite / PostgreSQL)
│   ├── models.py                 # ORM Models (Tickets, Knowledge Base articles)
│   ├── schemas.py                # Pydantic request/response schemas
│   ├── main.py                   # FastAPI application and REST endpoints
│   └── services/
│       ├── knowledge_base.py     # Search engine and KB ingestion service
│       ├── query_orchestrator.py # Query orchestration pipeline
│       ├── ai_assistant.py       # Optional AI module (LLM RAG)
│       ├── email_service.py      # Multi-channel SMTP notifications
│       ├── telegram_relay.py     # Backend-to-Telegram notification relay
│       └── ticket_service.py     # Ticket lifecycle management
├── bot/
│   ├── api_client.py             # Asynchronous HTTP client targeting the backend
│   ├── keyboards.py              # Telegram inline keyboards (YES / NO)
│   ├── main.py                   # Telegram bot entrypoint (aiogram 3)
│   ├── utils.py                  # Markdown escaping and Telegram utilities
│   └── handlers/
│       ├── user_handlers.py      # Handlers for private user chats
│       └── support_handlers.py   # Handlers for the support team group
├── tests/                        # Unit, integration, resilience, and E2E test suite
├── Dockerfile                    # Production-ready Docker container image
├── docker-compose.yml            # Multi-service deployment (backend + bot)
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variables template
```

---

## Installation & Quick Start

### 1. Clone and Set Up Environment

```bash
# Clone the repository
git clone <repo_url>
cd chatbot

# Create a virtual environment
virtualenv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration template
cp .env.example .env
```

### 2. Configure the `.env` File

Edit the `.env` file with your Telegram bot credentials:
```ini
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_SUPPORT_GROUP_ID=-1001234567890

# Optional: Enable AI Module
AI_ENABLED=false
AI_API_KEY=
AI_PROVIDER=gemini
```

> **Tip to find your `TELEGRAM_SUPPORT_GROUP_ID`:**
> 1. Create a Telegram group for your support team and add your bot as a member.
> 2. Send any message in the group, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` to inspect `chat.id` (a negative integer starting with `-100`).

### 3. Launch Services

#### Local Development Mode:
```bash
# Terminal 1: Start the backend API
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start the Telegram Bot
python -m bot.main
```

#### Docker Compose Mode:
```bash
docker compose up --build -d
```

---

## Testing & Verification

The automated test suite covers unit tests, database migrations, API endpoints, LLM resilience, and the full end-to-end (E2E) lifecycle loop:

```bash
pytest -v
```
