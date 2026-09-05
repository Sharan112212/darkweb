"""
Database migrations package.
"""

from db.migrations.initial_schema import run_migration

__all__ = ["run_migration"]
