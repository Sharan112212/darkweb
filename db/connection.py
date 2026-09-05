"""
Database connection factory and unified wrapper for SIH26151.
Supports SQLite (development/testing) and PostgreSQL (production).
"""

import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

# Optional driver imports
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    RealDictCursor = None
    PSYCOPG2_AVAILABLE = False

try:
    import sqlalchemy
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    sqlalchemy = None
    SQLALCHEMY_AVAILABLE = False


def _adapt_sql_for_postgres(sql: str) -> str:
    """
    Translates SQLite parameter marker '?' to PostgreSQL '%s'
    while preserving '?' inside string literals.
    """
    parts = sql.split("'")
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("?", "%s")
    return "'".join(parts)


def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
    """Convert a database row (sqlite3.Row or psycopg2 dict or tuple) to a dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


class DatabaseConnection:
    """
    Unified database connection wrapper providing identical semantics across
    SQLite and PostgreSQL connections.
    """

    def __init__(self, raw_connection: Any, db_type: str = "sqlite", url: Optional[str] = None):
        self._conn = raw_connection
        self.db_type = db_type.lower()
        self.url = url

    @property
    def raw_connection(self) -> Any:
        """Access the underlying database-specific connection instance."""
        return self._conn

    @property
    def is_sqlite(self) -> bool:
        return self.db_type == "sqlite"

    @property
    def is_postgres(self) -> bool:
        return self.db_type in ("postgres", "postgresql")

    def execute(self, sql: str, params: Union[Tuple, List, Dict, None] = None) -> Any:
        """
        Execute a SQL statement with parameter binding.
        Transparently handles placeholder translation (? to %s for PostgreSQL).
        """
        query = sql
        if self.is_postgres:
            query = _adapt_sql_for_postgres(sql)

        cur = self._conn.cursor()
        if params is not None:
            cur.execute(query, params)
        else:
            cur.execute(query)
        return cur

    def executemany(self, sql: str, param_list: Iterable) -> Any:
        """Execute a SQL statement against multiple parameter sets."""
        query = sql
        if self.is_postgres:
            query = _adapt_sql_for_postgres(sql)

        cur = self._conn.cursor()
        cur.executemany(query, param_list)
        return cur

    def executescript(self, script: str) -> None:
        """Execute a multi-statement SQL script."""
        if self.is_sqlite:
            self._conn.executescript(script)
        else:
            cur = self._conn.cursor()
            cur.execute(script)
            self._conn.commit()
            cur.close()

    def fetchone(self, sql: str, params: Union[Tuple, List, Dict, None] = None) -> Optional[Dict[str, Any]]:
        """Execute a query and fetch a single result as a Python dict."""
        cur = self.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return _row_to_dict(row)

    def fetchall(self, sql: str, params: Union[Tuple, List, Dict, None] = None) -> List[Dict[str, Any]]:
        """Execute a query and fetch all results as a list of Python dicts."""
        cur = self.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return [_row_to_dict(r) for r in rows if r is not None]

    def commit(self) -> None:
        """Commit the current transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def cursor(self) -> Any:
        """Return a native cursor."""
        return self._conn.cursor()

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    def __getattr__(self, name: str) -> Any:
        """Delegate unhandled methods or properties to the raw connection."""
        return getattr(self._conn, name)


def get_connection(db_path_or_url: Optional[Union[str, DatabaseConnection, Any]] = None) -> DatabaseConnection:
    """
    Factory function returning a unified DatabaseConnection.

    Supported inputs:
    - None: Resolves from DATABASE_URL -> DB_PATH -> local SQLite file (darkweb_intel.db)
    - DatabaseConnection: Returned directly
    - sqlite3.Connection: Wrapped in DatabaseConnection
    - 'postgresql://...' or 'postgres://...': PostgreSQL connection via psycopg2/sqlalchemy
    - 'sqlite://...' or local path: SQLite connection via sqlite3
    """
    if isinstance(db_path_or_url, DatabaseConnection):
        return db_path_or_url

    if isinstance(db_path_or_url, sqlite3.Connection):
        db_path_or_url.row_factory = sqlite3.Row
        return DatabaseConnection(db_path_or_url, db_type="sqlite")

    target = db_path_or_url
    if target is None:
        target = os.environ.get("DATABASE_URL") or os.environ.get("DB_PATH")
        if not target:
            # Default to project root darkweb_intel.db
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            target = os.path.join(project_root, "darkweb_intel.db")

    target_str = str(target).strip()

    # PostgreSQL detection
    if target_str.startswith("postgresql://") or target_str.startswith("postgres://"):
        if PSYCOPG2_AVAILABLE:
            conn = psycopg2.connect(target_str, cursor_factory=RealDictCursor)
            return DatabaseConnection(conn, db_type="postgresql", url=target_str)
        elif SQLALCHEMY_AVAILABLE:
            engine = sqlalchemy.create_engine(target_str)
            conn = engine.raw_connection()
            return DatabaseConnection(conn, db_type="postgresql", url=target_str)
        else:
            raise ImportError(
                "PostgreSQL connection requested (" + target_str.split("@")[-1] + "), "
                "but neither 'psycopg2' nor 'sqlalchemy' is installed. "
                "Please run 'pip install psycopg2-binary'."
            )

    # SQLite connection handling
    sqlite_path = target_str
    if sqlite_path.startswith("sqlite:///"):
        sqlite_path = sqlite_path[10:]
    elif sqlite_path.startswith("sqlite://"):
        sqlite_path = sqlite_path[9:]
    elif sqlite_path.startswith("sqlite:"):
        sqlite_path = sqlite_path[7:]

    if sqlite_path != ":memory:":
        abs_path = os.path.abspath(sqlite_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        sqlite_path = abs_path

    raw_conn = sqlite3.connect(sqlite_path, check_same_thread=False, timeout=30.0)
    raw_conn.row_factory = sqlite3.Row
    raw_conn.execute("PRAGMA foreign_keys = ON;")

    return DatabaseConnection(raw_conn, db_type="sqlite", url=sqlite_path)


# Compatibility aliases
get_db_connection = get_connection
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "darkweb_intel.db")

