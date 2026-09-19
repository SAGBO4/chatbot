<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/stack-logo-white.png">
  <source media="(prefers-color-scheme: light)" srcset="frontend/public/stack-logo-full.png">
  <img alt="Stack Wallet" src="frontend/public/stack-logo-full.png" width="220">
</picture>

<h1><img src="frontend/public/stack-wallet-bot.png" width="54" alt="Stack Wallet Bot" valign="middle"> Changelog</h1>

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

No version has been tagged yet, so changes are listed under **Unreleased**, and the history before that is grouped by date.

## [Unreleased]

### Added
- Community files: [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1), [SECURITY.md](SECURITY.md), issue forms and a pull request template.
- CI: a `frontend` job (`npm ci`, lint, build) next to the backend job.
- `frontend/.env.example` and documentation of the frontend proxy: `BACKEND_API_URL`, `BACKEND_API_KEY`, `TELEGRAM_BOT_TOKEN`, and who can do what through it.
- Docstrings on the backend API routes (4 of 21 operations had a description in the generated OpenAPI schema, all 21 do now), services, models and bot handlers; the knowledge base scoring formula is documented.
- Stack Wallet banners and bot illustrations in the READMEs and community files; a Mermaid diagram of the support flow.
- `"license": "MIT"` in `frontend/package.json`.

### Changed
- **Dependencies:** `backend/requirements.txt` is now runtime-only, with floors raised to the versions the tests actually run against (they were still `fastapi>=0.110`, `pydantic>=2.6`...), and no longer lists `python-dotenv` (pulled in by `pydantic-settings`). New `backend/requirements-dev.txt` for `pytest`, `pytest-asyncio`, `pytest-cov`, `mutmut`, `ruff`, `bandit`, `semgrep` and `pip-audit`: the README already asked for them but none was declared. CI installs it instead of a bare `pip install ruff`. `requirements.lock` was regenerated: same versions, minus `pytest` and its dependencies, so the Docker image no longer ships a test runner.
- **Breaking:** the Python package `backend/backend/` is now `backend/app/`. The server entrypoint is `uvicorn app.main:app` (was `backend.main:app`); update any script, Docker command or import that used the old name.
- The single 275-line README, duplicated in `backend/`, is split into a root README (overview, quickstart), `backend/README.md` and `frontend/README.md`.
- CI: `ruff check .` now fails the build on lint errors (it was ignored with `|| true`).
- `.gitignore`: every `.env*` file is ignored except `.env.example`; OS files (`.DS_Store`, `Thumbs.db`) too.
- `.env.example`: `AI_PROVIDER=gemini`.
- The test-count claims in the docs now say "400+" instead of a number that goes stale.
- **Production compose stack:** `POSTGRES_PASSWORD` is now required (it silently defaulted to `postgres`), and the API is published on `127.0.0.1:8000` instead of all interfaces, so it is reachable only through the reverse proxy. Documented `POSTGRES_*` in `.env.example`.

### Removed
- Internal spec-driven-development scaffolding: `.agents/` and `openspec/`.
- `backend/TODO.md` (a personal, outdated checklist), `backend/LICENSE` and `backend/.env.example` (identical copies of the root files).
- Unused create-next-app SVGs and the unused `StackLogo` component in the frontend.

### Fixed
- Docs said the Dockerfile was multi-stage; it is not.
- A test that checks the Brevo token never appears in application logs could pass without checking anything if no log was captured; it now asserts that logs were captured.
- Backend docstrings and comments that described behavior the code does not have (Alembic "not used", "normalized" and "top" keywords in the knowledge base, `is_authorized` allowing whitelist management, the API key "sent even if unset", `/purge` deleting any bot message) were corrected, and comments pointing at deleted spec documents were removed.
- `frontend/README.md` listed six backend endpoints that do not exist; it now lists the ones the frontend calls.
- Bot: `/mute`, `/unmute`, `/ban`, `/kick` and `/warn` sent as a reply to a member's message were ignored, and so was a question asked as a reply in a private chat. The support-group reply handler was consuming every reply in every chat.
- `deploy/Caddyfile` did not redact anything: the `token` query parameter was written to the access log in clear text (tested with Caddy 2.11). It now redacts the query secrets and the `X-Webhook-Token`, `X-Brevo-Token` and `X-Api-Key` headers.
- **The backend silenced its own logs after startup.** The Alembic migration runs in the API process, and `alembic/env.py` called `logging.config.fileConfig()` with its default `disable_existing_loggers=True`, which disabled every logger created before it: `app.main`, all services, `httpx` and `uvicorn.error`. Errors such as "Background task failed" or "Failed to relay message" never reached a handler. Reproduced, fixed, and covered by a test that runs the real migration.
- **Every message the bot or the API writes now follows `/language`.** Besides the buttons, these were still French only: the `...(tronqué)` marker, the support group ticket card, the throttling notices, the query fallbacks ("no answer found", "ask a question"), the emails sent to the support team, and the Telegram notices sent when a ticket is resolved by email. Emails and query fallbacks read the persisted bot language; French output is unchanged. The support group card keeps `TICKET #<id>` and `ID: <user id>` in every language, because the support handler parses them from the card text. The LLM prompts are now written in English (they still tell the model to answer in the language of the question).
- **Internal:** `app/i18n.py` and `app/telegram_text.py` moved from `bot/` so that the API no longer imports the bot package; a test enforces it.
- Bot: the YES / NO buttons under every answer and the `/webapp` button and messages were hard-coded in French; with `/language en` the text said "click YES" while the buttons read OUI / NON. They now follow the active language (the `callback_data` is unchanged, so buttons on old messages keep working).
- Bot and API robustness: `/BTC` (any casing) is now recognised like `/btc`; `AI_PROVIDER=OpenAI` no longer silently disables voice transcription while enabling AI answers; the task that removes the YES / NO buttons after a timeout is kept referenced so it cannot be garbage-collected mid-sleep; the Brevo webhook no longer returns the text of an internal exception to its caller (it stays in the server logs).
- The Telegram bot token could leak: it is part of every Bot API URL (`/bot<token>/sendMessage`), `httpx` logs that URL at INFO, and with `SENTRY_DSN` set every Sentry event that followed a Telegram call carried it in an HTTP breadcrumb (reproduced, then covered by tests). Logs and Sentry payloads (events, transactions, breadcrumbs) are now scrubbed by the new `app/observability.py`, which also replaces the two copies of the Sentry initialisation. If the token was ever sent to Sentry, rotate it with @BotFather.
- Five routing tests passed without checking anything because the bot's throttling was dropping their messages; they now use separate users and assert no throttling happened.

## Earlier history (2026-09-12 to 2026-09-18)

### 2026-09-18
- Community group features: `/ask` Q&A with expiring YES/NO buttons, moderation (`/mute`, `/unmute`, `/ban`, `/kick`, `/warn`, `/purge`), crypto prices (`/btc`, `/eth`, `/firo`, ...).
- Dynamic community group setup with `/setup_community`, an owner (`BOT_OWNER_TELEGRAM_ID`) and an admin whitelist; French and English bot messages with `/language`.
- Mobile-first Next.js WebApp for Telegram Mini App with a monochrome glassmorphism design.
- Email support made optional: the bot can run in pure Telegram mode.
- Security: admin role cache window fixed, ticket resolution rate-limited, auth and IDOR gaps hardened, the frontend moved behind a same-origin proxy that keeps the API key server-side and verifies Telegram `initData`.

### 2026-09-16
- Ticket retrieval scoped by `user_id` to prevent IDOR.
- Brevo inbound webhook: header-based token authentication, log redaction of secrets, and isolated background tasks.
- Quality tooling: mutation testing (mutmut), bandit and semgrep annotations resolved, a dependency lockfile for security scanning, and a large hermetic test suite covering the bot, email, knowledge base, webhooks, tickets and rate limiting.

### 2026-09-14
- Backend infrastructure: Alembic migrations, connection pooling, PostgreSQL support with a production Docker Compose stack, request rate limiting, health check that pings the database, GitHub Actions CI.
- Several rounds of review fixes: SQLite locking and WAL mode, transactional atomicity, input validation, email parsing, bilingual search, feedback deduplication.
- README translated to English.

### 2026-09-12 to 2026-09-13
- First version: Telegram support bot with a knowledge base and a feedback loop that indexes every agent solution.
- Dual-channel ticketing: Telegram support group and email, kept in sync; Brevo inbound email webhook.
- Optional AI answers and speech-to-text for agents' voice replies.
- Hardened ticket resolution authorization.
