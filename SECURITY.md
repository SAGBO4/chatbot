<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/stack-logo-white.png">
  <source media="(prefers-color-scheme: light)" srcset="frontend/public/stack-logo-full.png">
  <img alt="Stack Wallet" src="frontend/public/stack-logo-full.png" width="220">
</picture>

<h1><img src="frontend/public/stack-wallet-security.png" width="54" alt="Security Policy" valign="middle"> Security Policy</h1>

## Supported Versions

There are no released versions — this project ships continuously from the `main` branch. Only the latest commit on `main` is supported; please make sure you're up to date before reporting an issue.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, email either:
- michael.sagbo@epitech.eu
- kantegilchrist@gmail.com

Include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce it (endpoint, payload, Telegram command — whatever applies).
- Any relevant logs, with secrets/tokens redacted.

This is a small project maintained on a best-effort basis — there's no guaranteed response time, but we'll do our best to acknowledge reports promptly and keep you updated as we work on a fix.

## What's already in place

CI runs `ruff` and the test suite on every change, and the suite covers the security-relevant behavior (authentication that fails closed, IDOR scoping, webhook signatures, rate limiting, secrets kept out of logs and error responses).

These scanners are run by the maintainers, not by CI yet:
- `bandit` — Python AST security linter
- `semgrep` — semantic multi-rule security analysis
- `trivy` — dependency vulnerability and secret scanning
- `pip-audit` — PyPA advisory vulnerability scanner

See [backend/README.md](backend/README.md#testing--verification) for how to run them locally. Application-level protections (IDOR access control, webhook signature verification, rate limiting, access log redaction) are documented in the same file.
