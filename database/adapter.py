"""Multi-database adapter interface.

Provides a uniform interface for connecting, discovering schema, and executing
read-only queries against different database backends.

Implemented:
    - PostgreSQL  (fully working)

Stubbed (interface only — raises NotImplementedError):
    - MySQL
    - SQLite
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.schema_catalog import (
    ColumnInfo,
    DatabaseSchema,
    ForeignKey,
    TableInfo,
)


class DatabaseAdapter(ABC):
    """Abstract interface that every database backend must implement."""

    @abstractmethod
    def connect(self, url: str) -> Any:
        """Connect to the database and return a connection object."""

    @abstractmethod
    def discover_schema(self, connection: Any) -> DatabaseSchema:
        """Introspect the live connection and return a ``DatabaseSchema``."""

    @abstractmethod
    def execute_readonly(
        self, connection: Any, sql: str, params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Run a read-only query and return rows as dicts."""

    @abstractmethod
    def validate_query(self, sql: str, schema: DatabaseSchema) -> Optional[str]:
        """Return ``None`` if the query is safe, or an error message."""

    @abstractmethod
    def set_timeout(self, connection: Any, timeout_ms: int) -> None:
        """Set a per-connection query timeout."""

    @abstractmethod
    def get_database_name(self, connection: Any) -> Optional[str]:
        """Return the name of the currently connected database."""

    @abstractmethod
    def close(self, connection: Any) -> None:
        """Close the connection."""

    @abstractmethod
    def is_alive(self, connection: Any) -> bool:
        """Return True if the connection is usable."""

    @property
    @abstractmethod
    def db_type(self) -> str:
        """Short label like 'postgresql', 'mysql', 'sqlite'."""

    @property
    @abstractmethod
    def is_stub(self) -> bool:
        """True for backends that are not yet fully implemented."""


# ---------------------------------------------------------------------------
# PostgreSQL — full implementation
# ---------------------------------------------------------------------------

class PostgreSQLAdapter(DatabaseAdapter):
    """Fully working PostgreSQL adapter using *psycopg*."""

    SUPPORTED_SCHEMES = frozenset({
        "postgresql", "postgres", "postgresql+psycopg", "postgresql+psycopg2",
    })

    @property
    def db_type(self) -> str:
        return "postgresql"

    @property
    def is_stub(self) -> bool:
        return False

    def connect(self, url: str) -> Any:
        try:
            import psycopg  # type: ignore[import-untyped]
        except ImportError:
            try:
                import psycopg2 as psycopg  # type: ignore[import-untyped]
            except ImportError:
                raise RuntimeError(
                    "PostgreSQL adapter requires psycopg (or psycopg2) to be installed."
                )

        conn = psycopg.connect(url, connect_timeout=10, autocommit=True)
        return conn

    def get_database_name(self, connection: Any) -> Optional[str]:
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT current_database()")
                row = cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def is_alive(self, connection: Any) -> bool:
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self, connection: Any) -> None:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def set_timeout(self, connection: Any, timeout_ms: int) -> None:
        try:
            with connection.cursor() as cur:
                cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
        except Exception:
            pass

    # -- Schema discovery ----------------------------------------------------

    def discover_schema(self, connection: Any) -> DatabaseSchema:
        schema = DatabaseSchema()
        if connection is None:
            return schema

        schema.database_type = "postgresql"
        schema.database_name = self.get_database_name(connection)

        with connection.cursor() as cur:
            self._discover_columns(cur, schema)
            self._discover_primary_keys(cur, schema)
            self._discover_foreign_keys(cur, schema)
            self._discover_table_comments(cur, schema)

        return schema

    def _discover_columns(self, cur: Any, schema: DatabaseSchema) -> None:
        try:
            cur.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable,
                       column_default,
                       col_description(
                           (table_schema || '.' || table_name)::regclass,
                           ordinal_position
                       ) as column_comment
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                ORDER BY table_name, ordinal_position
                """
            )
            for row in cur.fetchall():
                table_name, col_name, data_type, is_nullable, default, comment = row
                col_info = ColumnInfo(
                    name=col_name,
                    data_type=data_type or "",
                    is_nullable=(is_nullable == "YES"),
                    column_default=default,
                    comment=comment,
                )
                if table_name not in schema.tables:
                    schema.tables[table_name] = TableInfo(name=table_name)
                schema.tables[table_name].columns.append(col_info)
        except Exception:
            # Fallback without col_description
            cur.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                ORDER BY table_name, ordinal_position
                """
            )
            for row in cur.fetchall():
                table_name, col_name, data_type, is_nullable, default = row
                col_info = ColumnInfo(
                    name=col_name,
                    data_type=data_type or "",
                    is_nullable=(is_nullable == "YES"),
                    column_default=default,
                )
                if table_name not in schema.tables:
                    schema.tables[table_name] = TableInfo(name=table_name)
                schema.tables[table_name].columns.append(col_info)

    def _discover_primary_keys(self, cur: Any, schema: DatabaseSchema) -> None:
        try:
            cur.execute(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = current_schema()
                ORDER BY tc.table_name, kcu.ordinal_position
                """
            )
            for table_name, column_name in cur.fetchall():
                if table_name in schema.tables:
                    schema.tables[table_name].primary_keys.append(column_name)
        except Exception:
            pass

    def _discover_foreign_keys(self, cur: Any, schema: DatabaseSchema) -> None:
        try:
            cur.execute(
                """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = current_schema()
                ORDER BY tc.table_name, kcu.column_name
                """
            )
            for tname, col, ref_tname, ref_col in cur.fetchall():
                schema.foreign_keys.append(
                    ForeignKey(
                        table=tname,
                        column=col,
                        ref_table=ref_tname,
                        ref_column=ref_col,
                    )
                )
        except Exception:
            pass

    def _discover_table_comments(self, cur: Any, schema: DatabaseSchema) -> None:
        try:
            cur.execute(
                """
                SELECT c.relname, obj_description(c.oid, 'pg_class')
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r' AND n.nspname = current_schema()
                """
            )
            for table_name, comment in cur.fetchall():
                if table_name in schema.tables and comment:
                    schema.tables[table_name].comment = comment
        except Exception:
            pass

    # -- Query execution -----------------------------------------------------

    def execute_readonly(
        self, connection: Any, sql: str, params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        with connection.cursor() as cur:
            cur.execute(sql, params or [])
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []

        result: List[Dict[str, Any]] = []
        for row in rows:
            item: Dict[str, Any] = {}
            for idx, column in enumerate(columns):
                value = row[idx]
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                elif type(value).__name__ == "Decimal":
                    value = float(value)
                item[column] = value
            result.append(item)
        return result

    def validate_query(self, sql: str, schema: DatabaseSchema) -> Optional[str]:
        """Validate that a SQL string is safe and references known objects."""
        cleaned = sql.strip().rstrip(";").lower()

        if not cleaned.startswith("select"):
            return "Only SELECT queries are allowed."

        if ";" in cleaned:
            return "Multiple SQL statements are not allowed."

        forbidden = [
            " insert ", " update ", " delete ", " drop ", " alter ",
            " truncate ", " create ", " grant ", " revoke ",
            " execute ", " copy ", " set ", " reset ",
        ]
        padded = f" {cleaned} "
        for token in forbidden:
            if token in padded:
                return f"Blocked SQL operation detected: {token.strip()}"

        return None


# ---------------------------------------------------------------------------
# MySQL — stub
# ---------------------------------------------------------------------------

class MySQLAdapter(DatabaseAdapter):
    """Stub adapter — not yet implemented."""

    @property
    def db_type(self) -> str:
        return "mysql"

    @property
    def is_stub(self) -> bool:
        return True

    def connect(self, url: str) -> Any:
        raise NotImplementedError(
            "MySQL adapter is not yet implemented. "
            "Install a MySQL driver (e.g. mysql-connector-python or pymysql) and implement this class."
        )

    def discover_schema(self, connection: Any) -> DatabaseSchema:
        raise NotImplementedError("MySQL schema discovery is not yet implemented.")

    def execute_readonly(self, connection: Any, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError("MySQL query execution is not yet implemented.")

    def validate_query(self, sql: str, schema: DatabaseSchema) -> Optional[str]:
        raise NotImplementedError("MySQL query validation is not yet implemented.")

    def set_timeout(self, connection: Any, timeout_ms: int) -> None:
        raise NotImplementedError("MySQL timeout is not yet implemented.")

    def get_database_name(self, connection: Any) -> Optional[str]:
        raise NotImplementedError("MySQL get_database_name is not yet implemented.")

    def close(self, connection: Any) -> None:
        raise NotImplementedError("MySQL close is not yet implemented.")

    def is_alive(self, connection: Any) -> bool:
        return False


# ---------------------------------------------------------------------------
# SQLite — stub
# ---------------------------------------------------------------------------

class SQLiteAdapter(DatabaseAdapter):
    """Stub adapter — not yet implemented."""

    @property
    def db_type(self) -> str:
        return "sqlite"

    @property
    def is_stub(self) -> bool:
        return True

    def connect(self, url: str) -> Any:
        raise NotImplementedError(
            "SQLite adapter is not yet implemented. "
            "Use the built-in sqlite3 module to implement this class."
        )

    def discover_schema(self, connection: Any) -> DatabaseSchema:
        raise NotImplementedError("SQLite schema discovery is not yet implemented.")

    def execute_readonly(self, connection: Any, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError("SQLite query execution is not yet implemented.")

    def validate_query(self, sql: str, schema: DatabaseSchema) -> Optional[str]:
        raise NotImplementedError("SQLite query validation is not yet implemented.")

    def set_timeout(self, connection: Any, timeout_ms: int) -> None:
        raise NotImplementedError("SQLite timeout is not yet implemented.")

    def get_database_name(self, connection: Any) -> Optional[str]:
        raise NotImplementedError("SQLite get_database_name is not yet implemented.")

    def close(self, connection: Any) -> None:
        raise NotImplementedError("SQLite close is not yet implemented.")

    def is_alive(self, connection: Any) -> bool:
        return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

ADAPTERS: Dict[str, type] = {
    "postgresql": PostgreSQLAdapter,
    "postgres": PostgreSQLAdapter,
    "mysql": MySQLAdapter,
    "sqlite": SQLiteAdapter,
}


def get_adapter(db_type: str) -> DatabaseAdapter:
    """Return an adapter instance for the given database type string.

    Raises ``ValueError`` for unknown types.
    """
    cls = ADAPTERS.get(db_type.lower().strip())
    if cls is None:
        supported = ", ".join(sorted(ADAPTERS.keys()))
        raise ValueError(
            f"Unsupported database type: {db_type!r}. Supported types: {supported}"
        )
    return cls()


def list_supported_adapters() -> Dict[str, Dict[str, Any]]:
    """Return metadata about all registered adapters."""
    result: Dict[str, Dict[str, Any]] = {}
    for name, cls in ADAPTERS.items():
        adapter = cls()
        result[name] = {
            "db_type": adapter.db_type,
            "is_stub": adapter.is_stub,
        }
    return result
