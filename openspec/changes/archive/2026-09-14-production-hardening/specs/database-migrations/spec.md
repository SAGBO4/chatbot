## ADDED Requirements

### Requirement: Multi-dialect database engine support
The database initialization and migration system SHALL support both SQLite (`sqlite+aiosqlite://`) and PostgreSQL (`postgresql+asyncpg://`) backends interchangeably based on configuration.

#### Scenario: Running against PostgreSQL engine
- **WHEN** `DATABASE_URL` specifies a PostgreSQL connection string
- **THEN** the system initializes async connection pools with PostgreSQL driver parameters, applies Alembic migrations compatible with Postgres types, and executes all ORM queries without dialect-specific errors

#### Scenario: Running against default SQLite engine
- **WHEN** `DATABASE_URL` specifies an SQLite database file
- **THEN** the system maintains full backward compatibility with SQLite WAL mode and schema auto-inspection
