# Alembic Migration Guide

## Overview

Alembic manages all database schema changes via migrations.

- **Initial migration**: `001_initial_schema.py` (creates all tables)
- **Future migrations**: Created with `alembic revision --autogenerate`
- **Applied via**: `alembic upgrade head`

## Installation & Initialization

Alembic is already installed via `make install` (includes `alembic==1.13.0`).

The alembic folder is already initialized and contains:
- `alembic/` — Migration environment (env.py, script.py.mako)
- `alembic/versions/` — Migration files
- `alembic.ini` — Configuration

## Running Migrations

### Apply all pending migrations

```bash
alembic upgrade head
```

Applies all migrations up to the latest revision.

### Check current revision

```bash
alembic current
```

Shows which revision is currently applied.

### View migration history

```bash
alembic history
```

Shows all applied and pending migrations.

### Rollback one revision

```bash
alembic downgrade -1
```

Rolls back the most recent migration.

### Rollback to base (no tables)

```bash
alembic downgrade base
```

Removes all tables (destructive!).

## Creating New Migrations

After modifying `src/storage/models.py`, create a new migration:

```bash
alembic revision --autogenerate -m "Descriptive message"
```

This:
1. Compares current models to database schema
2. Generates migration with diff
3. Creates file in `alembic/versions/`

Review the generated migration before applying:
```bash
# Review the migration file
cat alembic/versions/NNN_*.py

# Apply if it looks correct
alembic upgrade head
```

## Configuration

Configuration is in:
- `alembic.ini` — Alembic settings
- `alembic/env.py` — Migration environment (loads settings from `src.config`)

The setup automatically:
- Reads `DATABASE_URL` from `.env` via `src.config.settings.database.url`
- Uses async SQLAlchemy for migrations
- Maintains proper sequencing of migrations

## Troubleshooting

### "Alembic command not found"
Make sure virtual environment is activated and dependencies are installed:
```bash
source venv/bin/activate
make install
```

### "ModuleNotFoundError: src"
Ensure you're in project root directory:
```bash
cd /path/to/canva-notebooklm-agent
alembic current
```

### "Database connection refused"
Ensure PostgreSQL is running:
```bash
docker-compose up -d postgres
docker-compose logs postgres
```

### Migration doesn't match schema
This can happen if:
1. Models were modified but migration not created
2. Manual SQL changes were made outside of migrations

Solution:
1. Create new migration: `alembic revision --autogenerate`
2. Review and apply: `alembic upgrade head`

## Best Practices

1. **Always autogenerate** — Let Alembic detect schema changes
2. **Review before applying** — Check generated migration file
3. **Small migrations** — One logical change per migration
4. **Descriptive messages** — Use `--m "Add tenant_id index"`
5. **Test migrations locally** — Run on dev DB before production
6. **Keep migrations simple** — Avoid complex Python logic in migrations

## Initial Migration Reference

The initial migration (`001_initial_schema.py`) creates:
- Tenants
- Users  
- Workflows
- WorkflowTasks
- Designs
- AuditLogs
- QuotaUsage

With proper indexes, foreign keys, and cascading deletes.

See [docs/DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for schema details.

## See Also

- [Alembic Official Docs](https://alembic.sqlalchemy.org/)
- [ADR-009: PostgreSQL + JSONB](../ARCHITECTURE_DECISIONS.md#adr-009-postgresql-with-jsonb-for-semi-structured-data)
- `src/storage/database.py` — Database async setup
- `src/config.py` — Configuration management
