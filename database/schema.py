from __future__ import annotations

import re
from typing import Any, Dict, List, Set


SENSITIVE_FIELD_HINTS = {
    "password",
    "passwd",
    "token",
    "secret",
    "apikey",
    "api_key",
    "accesstoken",
    "access_token",
    "refreshtoken",
    "refresh_token",
    "creditcard",
    "credit_card",
    "authorization",
    "sessionid",
    "jwt",
    "privatekey",
    "private_key",
}


class SchemaInspector:
    """Safely inspects a PostgreSQL database without exposing raw values."""

    def __init__(self, database) -> None:
        self.database = database

    @staticmethod
    def _normalize_field_name(field_name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(field_name).lower())

    @classmethod
    def _is_sensitive_field(cls, field_name: str) -> bool:
        normalized = cls._normalize_field_name(field_name)
        for sensitive in SENSITIVE_FIELD_HINTS:
            if sensitive in normalized:
                return True
        return False

    @staticmethod
    def _normalize_pg_type(raw_type: str) -> str:
        if not raw_type:
            return "unknown"
        normalized = raw_type.lower().strip()
        mapping = {
            "int4": "integer",
            "int8": "bigint",
            "varchar": "text",
            "character varying": "text",
            "timestamp without time zone": "timestamp",
            "timestamp with time zone": "timestamptz",
            "bool": "boolean",
            "bytea": "bytea",
            "jsonb": "jsonb",
            "uuid": "uuid",
        }
        return mapping.get(normalized, normalized)

    def get_schema_names(self) -> List[str]:
        if self.database is None:
            return []
        with self.database.cursor() as cursor:
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema') ORDER BY schema_name;"
            )
            return [row[0] for row in cursor.fetchall()]

    def get_tables_for_schema(self, schema_name: str) -> List[str]:
        if self.database is None:
            return []
        with self.database.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name;",
                (schema_name,),
            )
            return [row[0] for row in cursor.fetchall()]

    def inspect_table(self, schema_name: str, table_name: str) -> Dict[str, Any]:
        if self.database is None:
            return {"name": table_name, "columns": {}}

        with self.database.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
                """,
                (schema_name, table_name),
            )
            rows = cursor.fetchall()

        columns: Dict[str, str] = {}
        for column_name, data_type, _udt_name in rows:
            if self._is_sensitive_field(column_name):
                columns[column_name] = "string [REDACTED]"
            else:
                columns[column_name] = self._normalize_pg_type(data_type or _udt_name)

        return {"name": table_name, "columns": columns}

    def get_safe_schema_summary(self, allowed_schemas: Set[str] | None = None, max_schemas: int = 20) -> Dict[str, Any]:
        if self.database is None:
            return {"connected": False, "database": "unknown", "schemas": []}

        schemas = self.get_schema_names()
        if allowed_schemas is not None:
            schemas = [name for name in schemas if name in allowed_schemas]
        schemas = schemas[:max_schemas]

        schema_summary = []
        for schema_name in schemas:
            tables = []
            for table_name in self.get_tables_for_schema(schema_name):
                tables.append(self.inspect_table(schema_name, table_name))
            schema_summary.append({"name": schema_name, "tables": tables})

        with self.database.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            db_name = cursor.fetchone()[0]

        return {"connected": True, "database": db_name, "schemas": schema_summary}
