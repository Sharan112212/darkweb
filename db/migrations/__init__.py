"""
Database migrations package.
"""

import importlib

_mod = importlib.import_module("db.migrations.001_initial_schema")
run_migration = _mod.run_migration

__all__ = ["run_migration"]
