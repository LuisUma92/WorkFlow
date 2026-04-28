"""
Schema migrations for the WorkFlow global database.

Each migration module exposes ``run_migration(engine) -> MigrationReport`` and
must be idempotent: re-running on a migrated DB is a no-op.
"""
