<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/stack-logo-white.png">
  <source media="(prefers-color-scheme: light)" srcset="frontend/public/stack-logo-full.png">
  <img alt="Stack Wallet" src="frontend/public/stack-logo-full.png" width="220">
</picture>

<h1><img src="frontend/public/stack-wallet-contributing.png" width="54" alt="Contributing Guide" valign="middle"> Contributing</h1>

Thanks for taking the time to contribute. This is a small project maintained on a best-effort basis, so please be patient with review times.

## Before you start

For anything beyond a small fix (new feature, behavior change, refactor), please open an issue first to discuss the approach. It saves everyone time compared to a PR that has to be redesigned in review.

## Project layout

This is a monorepo — see [README.md](README.md) for the architecture overview, then [backend/README.md](backend/README.md) or [frontend/README.md](frontend/README.md) for setup instructions specific to the part you're touching.

## Development setup

Follow the "Getting Started" section in the root [README.md](README.md) to get the backend, bot, and frontend running locally.

## Branch naming

Branches follow `<type>/<short-description>`, e.g. `fix/ci-rate-limiting-test`, `feat/frontend-telegram-webapp`, `docs/contributing-guide`.

## Commit messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description`, for example:

```
fix(bot): handle missing community group id gracefully
docs(readme): clarify docker compose production setup
feat(api): add pagination to knowledge base articles endpoint
```

Common types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`.

## Before opening a pull request

Run the checks that CI runs, so you're not waiting on a red build to find out:

**Backend**
```bash
cd backend
pip install -r requirements-dev.txt   # once: runtime dependencies + test and QA tools
ruff check .
pytest -v
```

**Frontend**
```bash
cd frontend
npm run lint
npm run build
```

If you added or changed backend behavior, add or update tests — see [backend/README.md](backend/README.md#testing--verification) for the full test/lint/security-scan suite.

## Opening the pull request

- Target the `dev` branch, not `main`.
- Describe what changed and why, not just what — the diff already shows what.
- Link the issue it addresses, if any.
- Add a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) for anything a user or a contributor would notice.
- Make sure CI is green before requesting review.

## Reporting bugs

Open an issue with: what you did, what you expected, what happened instead, and enough detail to reproduce it (Telegram command used, endpoint called, relevant log lines with secrets redacted).

For security vulnerabilities, do not open a public issue — see [SECURITY.md](SECURITY.md).
