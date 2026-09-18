<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/stack-logo-white.png">
    <source media="(prefers-color-scheme: light)" srcset="frontend/public/stack-logo-full.png">
    <img alt="Stack Wallet" src="frontend/public/stack-logo-full.png" width="260" valign="middle">
  </picture>
  &nbsp;&nbsp;&nbsp;
  <img src="frontend/public/stack-wallet-bot.png" width="100" alt="Stack Wallet Bot" valign="middle">
</p>

<h1 align="center">Telegram Support Bot with Knowledge Base & AI Feedback Loop</h1>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python" src="https://img.shields.io/badge/python-3.13-blue.svg">
  <img alt="Node" src="https://img.shields.io/badge/node-%3E%3D18.18-339933.svg">
  <img alt="Tests" src="https://img.shields.io/badge/tests-414%20passing-brightgreen.svg">
</p>

A support bot for Telegram that gets smarter over time: it answers questions from a knowledge base, escalates to your team the moment it's stuck, and learns from every resolution — so the next person asking the same thing gets an instant answer instead of another ticket.

---

## How it works

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

A user asks a question, the bot searches the knowledge base (optionally backed by an LLM), and shows a YES/NO button to confirm it actually helped. A "no" opens a ticket in your private support group — an agent just replies to that message, the user gets the answer, and it's indexed back into the knowledge base for next time.

## Highlights

- **Instant Telegram support** — ask a question, get an answer pulled straight from a knowledge base that keeps learning from every ticket a human resolves.
- **One-tap escalation** — if the bot's answer doesn't help, a single "No" opens a ticket in your private support group; agents resolve it by just replying.
- **Optional AI** — works out of the box with free lexical/semantic search, or plug in OpenAI, Gemini, or DeepSeek for LLM-powered answers.
- **Public community Q&A** — members ask `/ask <question>` right in a group chat; the bot answers publicly and only escalates privately when needed.
- **Moderation & crypto, built in** — `/mute`, `/ban`, `/warn`, `/purge`, plus live prices via `/btc`, `/eth`, `/firo`, and more.
- **No-redeploy setup** — point the bot at a new community group anytime with `/setup_community`, right from Telegram.
- **Bilingual out of the box** — every bot message ships in French and English, switchable with `/language`.
- **A real web portal** — a mobile-first Next.js WebApp (Telegram Mini App-ready) styled after Stack Wallet, for browsing tickets, the knowledge base, and settings.

The security and reliability details (webhook auth, IDOR protection, rate limiting, background task isolation...) live in [backend/README.md](backend/README.md), alongside setup instructions.

---

## Project Structure

```
├── backend/                      # Complete Python Backend Services — see backend/README.md
│   ├── backend/                  # FastAPI Application & Services
│   ├── bot/                      # Telegram Bot (aiogram 3)
│   ├── alembic/                  # Database schema migration revisions
│   ├── tests/                    # 414 test cases (unit, integration, resilience, E2E)
│   ├── scripts/                  # Management scripts (e.g. seed_knowledge_base.py)
│   ├── data/                     # Persistent storage directory
│   ├── deploy/                   # Reverse proxy configurations (Caddy / Nginx)
│   ├── Dockerfile                # Production multi-stage Docker image
│   ├── docker-compose.yml        # Multi-service local orchestrator
│   ├── docker-compose.prod.yml   # Production stack with PostgreSQL 16
│   └── requirements.txt          # Python dependencies
├── frontend/                     # Modern Next.js Mobile-First WebApp (B&W Glassmorphism) — see frontend/README.md
│   ├── src/
│   │   ├── app/                  # App Router routes (/, /tickets, /knowledge, /crypto, /settings)
│   │   ├── components/           # UI primitives, layout (Header, BottomNav, Drawer), cards
│   │   ├── lib/                  # Backend API client, i18n dictionaries, Telegram WebApp SDK
│   │   └── types/                # TypeScript shared models
│   ├── public/                   # Static assets & Stack Wallet icons
│   └── package.json              # Next.js 16, React 19, Tailwind CSS v4
└── .env.example                  # Environment variables template
```

Full breakdown of each part, install steps, configuration, tests, and deployment live in their own READMEs:
- [backend/README.md](backend/README.md) — FastAPI API, Telegram bot, database migrations, Docker, tests, production hardening.
- [frontend/README.md](frontend/README.md) — Next.js WebApp / Telegram Mini App.

---

## Getting Started

```bash
git clone <repo_url>
cd chatbot
```

Minimal path to a running stack (see the linked READMEs for full details, configuration options, and production setup):

```bash
# 1. Backend API + Telegram bot
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # then fill in TELEGRAM_BOT_TOKEN, TELEGRAM_SUPPORT_GROUP_ID, BOT_OWNER_TELEGRAM_ID
alembic upgrade head
python -m scripts.seed_knowledge_base
uvicorn backend.main:app --reload --port 8000   # terminal 1
python -m bot.main                              # terminal 2

# 2. Frontend
cd ../frontend
npm install
npm run dev                                     # terminal 3
```

See [backend/README.md](backend/README.md) for: community group setup (`/setup_community`), inbound email webhooks, Docker Compose (SQLite or production PostgreSQL), reverse proxy hardening, rate limiting, and the automated test suite.

---

## License

Released under the [MIT License](LICENSE).
