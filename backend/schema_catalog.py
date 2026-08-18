from __future__ import annotations

import re
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
class SchemaCatalog:
    tables: Dict[str, List[str]] = field(default_factory=dict)
    column_types: Dict[Tuple[str, str], str] = field(default_factory=dict)
    foreign_keys: List[ForeignKey] = field(default_factory=list)
    database_name: Optional[str] = None

    def table_names(self) -> Set[str]:
        return set(self.tables.keys())

    def columns_for(self, table: str) -> List[str]:
        return list(self.tables.get(table, []))

    def has_column(self, table: str, column: str) -> bool:
        return column in self.tables.get(table, [])

    def is_sensitive(self, column: str) -> bool:
        normalized = re.sub(r"[^a-z0-9_]", "", column.lower())
        return any(hint in normalized for hint in SENSITIVE_HINTS)

    def safe_columns(self, table: str) -> List[str]:
        return [col for col in self.columns_for(table) if not self.is_sensitive(col)]

    def find_numeric_columns(self, table: str) -> List[str]:
        numeric_types = {"integer", "bigint", "smallint", "numeric", "decimal", "real", "double precision", "money"}
        result = []
        for column in self.columns_for(table):
            col_type = self.column_types.get((table, column), "").lower()
            if col_type in numeric_types or any(token in col_type for token in ("int", "numeric", "decimal", "real", "double", "money")):
                if not self.is_sensitive(column):
                    result.append(column)
        return result

    def find_name_column(self, table: str) -> Optional[str]:
        preferred = [
            f"{table[:-1]}_name" if table.endswith("s") else f"{table}_name",
            "name",
            "title",
            "label",
        ]
        columns = self.columns_for(table)
        for candidate in preferred:
            if candidate in columns:
                return candidate
        for column in columns:
            if column.endswith("_name") and not self.is_sensitive(column):
                return column
        if table == "employees" and "first_name" in columns:
            return "first_name"
        return None

    def find_amount_column(self, table: str) -> Optional[str]:
        preferred = ["amount", "total_amount", "salary", "budget", "unit_price", "price", "revenue", "cost"]
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
                        # Normalize direction for SQL builder: from child side when possible.
                        if fk.table == prev and fk.ref_table == node:
                            path.append(fk)
                        else:
                            path.append(ForeignKey(fk.ref_table, fk.ref_column, fk.table, fk.column))
                        node = prev
                    path.reverse()
                    return path
                queue.append(nxt)
        return None

    def to_summary(self) -> Dict[str, Any]:
        return {
            "database": self.database_name,
            "tables": {
                table: [col for col in columns if not self.is_sensitive(col)]
                for table, columns in sorted(self.tables.items())
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


def load_schema_catalog(connection) -> SchemaCatalog:
    catalog = SchemaCatalog()
    if connection is None:
        return catalog

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()
        catalog.database_name = row[0] if row else None

        cursor.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
            ORDER BY table_name, ordinal_position
            """
        )
        for table_name, column_name, data_type in cursor.fetchall():
            catalog.tables.setdefault(table_name, []).append(column_name)
            catalog.column_types[(table_name, column_name)] = data_type or ""

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
            catalog.foreign_keys.append(
                ForeignKey(
                    table=table_name,
                    column=column_name,
                    ref_table=ref_table,
                    ref_column=ref_column,
                )
            )

    return catalog
