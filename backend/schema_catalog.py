from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


SENSITIVE_HINTS = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "sessionid",
    "jwt",
    "private_key",
    "credit_card",
}


@dataclass
class ForeignKey:
    table: str
    column: str
    ref_table: str
    ref_column: str


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool = True
    column_default: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class TableInfo:
    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    comment: Optional[str] = None

    @property
    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]


@dataclass
class DatabaseSchema:
    """Full schema representation for any database."""
    database_name: Optional[str] = None
    database_type: str = "postgresql"
    tables: Dict[str, TableInfo] = field(default_factory=dict)
    foreign_keys: List[ForeignKey] = field(default_factory=list)

    def table_names(self) -> Set[str]:
        return set(self.tables.keys())

    def columns_for(self, table: str) -> List[str]:
        info = self.tables.get(table)
        return info.column_names if info else []

    def has_column(self, table: str, column: str) -> bool:
        return column in self.columns_for(table)

    def get_column_type(self, table: str, column: str) -> str:
        info = self.tables.get(table)
        if info:
            for col in info.columns:
                if col.name == column:
                    return col.data_type
        return ""

    def is_sensitive(self, column: str) -> bool:
        normalized = re.sub(r"[^a-z0-9_]", "", column.lower())
        return any(hint in normalized for hint in SENSITIVE_HINTS)

    def safe_columns(self, table: str) -> List[str]:
        return [col for col in self.columns_for(table) if not self.is_sensitive(col)]

    def find_numeric_columns(self, table: str) -> List[str]:
        numeric_types = {
            "integer", "bigint", "smallint", "numeric", "decimal",
            "real", "double precision", "money",
        }
        result = []
        for column in self.columns_for(table):
            col_type = self.get_column_type(table, column).lower()
            if col_type in numeric_types or any(
                token in col_type
                for token in ("int", "numeric", "decimal", "real", "double", "money")
            ):
                if not self.is_sensitive(column):
                    result.append(column)
        return result

    def find_name_column(self, table: str) -> Optional[str]:
        """Find the best human-readable name column for a table."""
        preferred = [
            f"{table[:-1]}_name" if table.endswith("s") else f"{table}_name",
            "name",
            "title",
            "label",
            "full_name",
            "display_name",
        ]
        columns = self.columns_for(table)
        for candidate in preferred:
            if candidate in columns:
                return candidate
        for column in columns:
            if column.endswith("_name") and not self.is_sensitive(column):
                return column
        # Fallback: look for first_name/last_name pattern
        if "first_name" in columns:
            return "first_name"
        return None

    def find_amount_column(self, table: str) -> Optional[str]:
        """Find the best numeric/money column for a table."""
        preferred = [
            "amount", "total_amount", "salary", "budget", "unit_price",
            "price", "revenue", "cost", "payment", "total", "value",
            "income", "expense", "fee", "charge", "rate", "profit",
            "balance", "wage", "bonus", "commission", "margin",
        ]
        columns = self.columns_for(table)
        for candidate in preferred:
            if candidate in columns:
                return candidate
        numeric = self.find_numeric_columns(table)
        for column in numeric:
            if column.endswith("_id") or column in {"id"}:
                continue
            return column
        return None

    def find_status_column(self, table: str) -> Optional[str]:
        for column in self.columns_for(table):
            if "status" in column.lower():
                return column
        return None

    def join_path(self, start: str, end: str) -> Optional[List[ForeignKey]]:
        if start == end:
            return []
        # BFS over undirected FK graph.
        edges: Dict[str, List[ForeignKey]] = {}
        for fk in self.foreign_keys:
            edges.setdefault(fk.table, []).append(fk)
            reverse = ForeignKey(fk.ref_table, fk.ref_column, fk.table, fk.column)
            edges.setdefault(fk.ref_table, []).append(reverse)

        queue = [start]
        parent: Dict[str, Tuple[str, ForeignKey]] = {}
        seen = {start}
        while queue:
            current = queue.pop(0)
            for edge in edges.get(current, []):
                nxt = edge.ref_table
                if nxt in seen:
                    continue
                seen.add(nxt)
                parent[nxt] = (current, edge)
                if nxt == end:
                    path: List[ForeignKey] = []
                    node = end
                    while node != start:
                        prev, fk = parent[node]
                        if fk.table == prev and fk.ref_table == node:
                            path.append(fk)
                        else:
                            path.append(
                                ForeignKey(fk.ref_table, fk.ref_column, fk.table, fk.column)
                            )
                        node = prev
                    path.reverse()
                    return path
                queue.append(nxt)
        return None

    def to_summary(self) -> Dict[str, Any]:
        return {
            "database": self.database_name,
            "database_type": self.database_type,
            "tables": {
                table: [col for col in info.column_names if not self.is_sensitive(col)]
                for table, info in sorted(self.tables.items())
            },
            "primary_keys": {
                table: info.primary_keys
                for table, info in sorted(self.tables.items())
                if info.primary_keys
            },
            "foreign_keys": [
                {
                    "table": fk.table,
                    "column": fk.column,
                    "ref_table": fk.ref_table,
                    "ref_column": fk.ref_column,
                }
                for fk in self.foreign_keys
            ],
        }


# ---------------------------------------------------------------------------
# Schema cache — avoids re-discovering schema on every request
# ---------------------------------------------------------------------------

class SchemaCache:
    """Caches the discovered schema with TTL and manual refresh support."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[DatabaseSchema, float]] = {}

    def get(self, connection_key: str) -> Optional[DatabaseSchema]:
        """Return cached schema if still valid, else None."""
        entry = self._cache.get(connection_key)
        if entry is None:
            return None
        schema, cached_at = entry
        if time.time() - cached_at > self.ttl_seconds:
            return None
        return schema

    def put(self, connection_key: str, schema: DatabaseSchema) -> None:
        """Store schema in cache."""
        self._cache[connection_key] = (schema, time.time())

    def invalidate(self, connection_key: Optional[str] = None) -> None:
        """Invalidate cache for a specific key or all."""
        if connection_key is None:
            self._cache.clear()
        else:
            self._cache.pop(connection_key, None)

    def get_or_discover(self, connection, connection_key: str) -> DatabaseSchema:
        """Return cached schema, or discover and cache it."""
        cached = self.get(connection_key)
        if cached is not None:
            return cached
        schema = _discover_schema(connection)
        self.put(connection_key, schema)
        return schema


# Global schema cache instance
schema_cache = SchemaCache(ttl_seconds=300)


# ---------------------------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------------------------

def _discover_schema(connection) -> DatabaseSchema:
    """Discover full schema from a live database connection.

    Works with any PostgreSQL database — no hardcoded table/column knowledge.
    """
    schema = DatabaseSchema()
    if connection is None:
        return schema

    with connection.cursor() as cursor:
        # Database name
        try:
            cursor.execute("SELECT current_database()")
            row = cursor.fetchone()
            schema.database_name = row[0] if row else None
        except Exception:
            pass

        # Database type detection (PostgreSQL for now)
        schema.database_type = "postgresql"

        # Discover all tables and columns
        try:
            cursor.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable,
                       column_default, col_description(
                           (table_schema || '.' || table_name)::regclass,
                           ordinal_position
                       ) as column_comment
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                ORDER BY table_name, ordinal_position
                """
            )
            for row in cursor.fetchall():
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
            # Fallback for databases without col_description
            cursor.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                ORDER BY table_name, ordinal_position
                """
            )
            for row in cursor.fetchall():
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

        # Discover primary keys
        try:
            cursor.execute(
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
            for table_name, column_name in cursor.fetchall():
                if table_name in schema.tables:
                    schema.tables[table_name].primary_keys.append(column_name)
        except Exception:
            pass

        # Discover foreign keys
        try:
            cursor.execute(
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
            for table_name, column_name, ref_table, ref_column in cursor.fetchall():
                schema.foreign_keys.append(
                    ForeignKey(
                        table=table_name,
                        column=column_name,
                        ref_table=ref_table,
                        ref_column=ref_column,
                    )
                )
        except Exception:
            pass

        # Table comments
        try:
            cursor.execute(
                """
                SELECT c.relname, obj_description(c.oid, 'pg_class')
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r' AND n.nspname = current_schema()
                """
            )
            for table_name, comment in cursor.fetchall():
                if table_name in schema.tables and comment:
                    schema.tables[table_name].comment = comment
        except Exception:
            pass

    return schema


def load_schema_catalog(connection) -> DatabaseSchema:
    """Load schema catalog with caching.

    This replaces the old function signature — now returns DatabaseSchema
    instead of SchemaCatalog, but provides backward-compatible methods.
    """
    cache_key = f"pg:{id(connection)}" if connection else "none"
    return schema_cache.get_or_discover(connection, cache_key)


def load_schema_catalog_no_cache(connection) -> DatabaseSchema:
    """Force a fresh schema discovery (for /schema refresh)."""
    cache_key = f"pg:{id(connection)}" if connection else "none"
    schema_cache.invalidate(cache_key)
    schema = _discover_schema(connection)
    schema_cache.put(cache_key, schema)
    return schema
