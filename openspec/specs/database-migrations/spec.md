# database-migrations Specification

## Purpose
Provides version-controlled, repeatable, and reversible relational database schema migrations for backend data models using Alembic.

## Requirements

### Requirement: Versioned schema migrations
The database management system SHALL execute schema migrations through ordered, tracked Alembic revisions matching the SQLAlchemy declarative models.

#### Scenario: Running pending database migrations on startup or CLI
- **WHEN** the backend application initializes or an operator runs the migration command
- **THEN** all unapplied Alembic revision scripts are applied in ascending order up to the latest revision (`head`)

#### Scenario: Existing deployment schema compatibility
- **WHEN** an existing database schema already contains tables
- **THEN** the migration baseline recognizes the existing schema without attempting redundant table creation

### Requirement: Multi-dialect database engine support
The database initialization and migration system SHALL support both SQLite (`sqlite+aiosqlite://`) and PostgreSQL (`postgresql+asyncpg://`) backends interchangeably based on configuration.

#### Scenario: Running against PostgreSQL engine
- **WHEN** `DATABASE_URL` specifies a PostgreSQL connection string
- **THEN** the system initializes async connection pools with PostgreSQL driver parameters, applies Alembic migrations compatible with Postgres types, and executes all ORM queries without dialect-specific errors

#### Scenario: Running against default SQLite engine
- **WHEN** `DATABASE_URL` specifies an SQLite database file
- **THEN** the system maintains full backward compatibility with SQLite WAL mode and schema auto-inspection
