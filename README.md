<p align="center">
  <img src="frontend/public/stack-wallet-bot.svg" width="140" alt="Stack Wallet Bot">
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/stack-logo-white.png">
    <source media="(prefers-color-scheme: light)" srcset="frontend/public/stack-logo-full.png">
    <img alt="Stack Wallet" src="frontend/public/stack-logo-full.png" width="300">
  </picture>
</p>

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
7. **Robust Background Isolation**: Asynchronous email dispatches and Telegram notifications run inside fault-isolated task wrappers, ensuring third-party network drops never crash the HTTP response lifecycle.
8. **IDOR Access Control**: User-scoped ticket retrieval (`?user_id=`) prevents unauthorized cross-user inspection while preserving administrative master access.
9. **Dual-Mode Webhook Security**: Brevo inbound emails authenticate via `X-Webhook-Token` / `X-Brevo-Token` headers or query parameters with automated access log token redaction.
10. **Community Group Q&A**: Members ask questions directly in a public community group via `/ask <question>`; the bot answers publicly, tagging the asker, with YES/NO resolution buttons that auto-expire after inactivity. Escalated tickets and all resolution/agent traffic stay confined to the private admin/support group or email — never posted to the community group.
11. **Crypto Market Data**: `/btc`, `/eth`, `/firo`, and other mapped asset commands return live price, 24h change, market cap, and 24h volume from CoinGecko, usable in DM or the community group.
12. **Community Moderation**: Admin-only `/mute`, `/unmute`, `/ban`, `/kick`, and `/warn` commands scoped to the community group, with admin status verified live against the Telegram Bot API. `/purge` lets a community-group admin delete recent bot messages without needing admin-group access.
13. **Dynamic Community Group Setup**: No redeploy needed to point the bot at a community — an env-defined owner (`BOT_OWNER_TELEGRAM_ID`) or an admin they whitelist runs `/setup_community` directly in the target group at any time. The admin/support group stays fixed via `.env` so ticket/moderation traffic can never be redirected by a chat command.
14. **Bilingual Bot (FR/EN)**: All bot-authored messages are available in French (default) and English; the owner or a whitelisted admin switches with `/language fr` or `/language en`.
15. **Telegram WebApp & Web Portal (Mobile-First)**: Dedicated Next.js web application styled with the official **Stack Wallet** monochrome branding and frosted glassmorphism. Designed mobile-first for seamless integration as a Telegram Mini App (Web App) with haptic feedback, safe area insets, compact header with drawer, and bottom navigation bar.

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
