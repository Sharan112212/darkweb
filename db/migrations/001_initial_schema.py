"""
Initial Schema Migration (001_initial_schema.py)
Executes DDL schema for SQLite or PostgreSQL.

Usage:
    python db/migrations/001_initial_schema.py [optional_db_path_or_url]
"""

import os
import sys
from typing import List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db.connection import get_connection


def run_migration(db_path_or_url: Optional[str] = None) -> List[str]:
    """
    Executes the initial database schema DDL against the specified target
    (SQLite database file or PostgreSQL URL).

    Returns a list of created/verified table names.
    """
    schema_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql")
    if not os.path.exists(schema_file):
        raise FileNotFoundError(f"Schema DDL file not found at: {schema_file}")

    with open(schema_file, "r", encoding="utf-8") as f:
        ddl_script = f.read()

    conn = get_connection(db_path_or_url)
    print(f"[*] Running migration 001_initial_schema against ({conn.db_type}): {conn.url or db_path_or_url}...")

    try:
        conn.executescript(ddl_script)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"[!] Migration failed with error: {exc}")
        raise

    # Verify tables
    verified_tables = []
    if conn.is_sqlite:
        rows = conn.fetchall("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        verified_tables = [r["name"] for r in rows if r]
    elif conn.is_postgres:
        rows = conn.fetchall("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        verified_tables = [r["table_name"] for r in rows if r]

    print(f"[+] Migration successful. Tables present in database ({len(verified_tables)}):")
    for tbl in sorted(verified_tables):
        print(f"    - {tbl}")

    conn.close()
    return verified_tables


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    tables = run_migration(target)
    sys.exit(0 if tables else 1)
