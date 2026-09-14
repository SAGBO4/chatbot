## 1. Rate Limiting and Anti-Spam

- [x] 1.1 Add `slowapi` to `requirements.txt` and install it in virtual environment
- [x] 1.2 Implement Aiogram throttling middleware (`bot/middlewares/throttling.py`) restricting user messages to 5 queries per 10 seconds per `user_id`
- [x] 1.3 Register throttling middleware in `bot/main.py` and handle flood warning messages gracefully
- [x] 1.4 Add `slowapi.Limiter` to `backend/main.py` applying rate limits on `/api/query` (30/minute) and `/api/tickets` (10/minute)
- [x] 1.5 Write automated tests in `tests/test_rate_limiting.py` verifying bot throttling and FastAPI 429 responses

## 2. PostgreSQL Scalability and Multi-Dialect Support

- [x] 2.1 Add `asyncpg` to `requirements.txt`
- [x] 2.2 Update `backend/database.py` to conditionally apply SQLite PRAGMAs (`WAL`, `busy_timeout`) only for SQLite URLs, and apply connection pooling parameters for PostgreSQL
- [x] 2.3 Verify `_add_missing_columns` schema inspector functions identically on PostgreSQL
- [x] 2.4 Add `docker-compose.prod.yml` configuring a PostgreSQL 16 service with volume persistence and healthcheck
- [x] 2.5 Update `README.md` and `TODO.md` with PostgreSQL configuration instructions and migration commands

## 3. Reverse Proxy Webhook Hardening (Brevo Token Protection)

- [x] 3.1 Create `deploy/nginx.conf` with a custom log format redacting or omitting query strings on `/api/webhooks/email-inbound/brevo`
- [x] 3.2 Create `deploy/Caddyfile` with an explicit access log directive excluding query parameters for the Brevo webhook path
- [x] 3.3 Add documentation in `TODO.md` and `README.md` explaining how to mount or apply these configurations on production reverse proxies

## 4. Monitoring, Alerting and Diagnostics

- [x] 4.1 Add `sentry-sdk` (with `fastapi` and `aiohttp` extras) to `requirements.txt`
- [x] 4.2 Add `SENTRY_DSN` configuration field to `backend/config.py`
- [x] 4.3 Initialize Sentry conditionally in `backend/main.py` lifespan and `bot/main.py` when `SENTRY_DSN` is provided
- [x] 4.4 Enhance `GET /health` in `backend/main.py` to execute a lightweight `SELECT 1` ping against the database and return detailed status (HTTP 200 ok, HTTP 503 if database disconnected)
- [x] 4.5 Write automated tests in `tests/test_monitoring.py` validating Sentry initialization bypass when unset, and `/health` error responses when database fails

## 5. End-to-End Verification and Documentation

- [x] 5.1 Run full test suite with `pytest` to guarantee zero regressions across existing 78 tests
- [x] 5.2 Validate OpenSpec change consistency with `openspec validate production-hardening`
