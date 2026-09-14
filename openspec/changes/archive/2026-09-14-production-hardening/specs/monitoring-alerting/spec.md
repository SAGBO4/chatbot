## Purpose

Provides operational observability, automated exception capture, and health metrics monitoring for production deployment.

## ADDED Requirements

### Requirement: Centralized error and exception reporting
The backend API and Telegram bot SHALL capture unhandled exceptions, downstream service timeouts, and background task errors and report them to a centralized monitoring system (such as Sentry) when configured.

#### Scenario: Unhandled exception occurs during query processing
- **WHEN** an unexpected exception occurs during request execution and `SENTRY_DSN` is configured
- **THEN** the system logs the full traceback, sends the event context to the monitoring service, and returns an appropriate error code to the caller

#### Scenario: Sentry is unconfigured
- **WHEN** `SENTRY_DSN` is not provided in environment variables
- **THEN** the system functions with standard structured logging without error or startup failure

### Requirement: Operational health check diagnostics
The `/health` endpoint SHALL provide comprehensive diagnostic details on service health, database connectivity, and configuration status.

#### Scenario: Database is reachable
- **WHEN** a health check request is made to `/health` and the database responds to a ping query
- **THEN** the response returns HTTP 200 with status ok and database connected

#### Scenario: Database is unreachable
- **WHEN** a health check request is made to `/health` while the database connection fails
- **THEN** the response returns HTTP 503 with database error status indicating service degradation
