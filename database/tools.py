from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


SENSITIVE_COLUMN_HINTS = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "authorization",
    "sessionid",
    "jwt",
    "private_key",
    "privatekey",
    "credit_card",
    "creditcard",
}


class DatabaseToolRegistry:
    """Controlled, read-only PostgreSQL operations for safe backend access."""

    def __init__(self, database, allowed_tables: Optional[Set[str]] = None, max_records: int = 100, query_timeout_ms: int = 5000) -> None:
        self.database = database
        self.allowed_tables = set(allowed_tables or self._discover_allowed_tables())
        self.max_records = max_records
        self.query_timeout_ms = query_timeout_ms

    @staticmethod
    def _normalize_name(value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", str(value).lower())

    @classmethod
    def _is_sensitive_column(cls, column_name: str) -> bool:
        normalized = cls._normalize_name(column_name)
        for sensitive in SENSITIVE_COLUMN_HINTS:
            if sensitive in normalized:
                return True
        return False

    @staticmethod
    def _is_sql_injection_candidate(value: Any) -> bool:
        if value is None:
            return False
        text = str(value)
        blocked = [";", "--", "/*", "*/", "\x00", "drop ", "delete ", "update ", "insert ", "alter ", "create "]
        lowered = text.lower()
        return any(token in lowered for token in blocked)

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        if not identifier or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            raise ValueError(f"Invalid identifier: {identifier!r}")
        return identifier

    def _discover_allowed_tables(self) -> Set[str]:
        if self.database is None:
            return set()
        try:
            with self.database.cursor() as cursor:
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' ORDER BY table_name;"
                )
                return {row[0] for row in cursor.fetchall()}
        except Exception:
            return set()

    def _validate_table(self, table_name: str) -> str:
        if not table_name:
            raise ValueError("Table name is required.")
        if self.allowed_tables and table_name not in self.allowed_tables:
            raise PermissionError(f"Table '{table_name}' is not allowed.")
        return self._quote_identifier(table_name)

    def _get_schema_columns(self, table_name: str) -> Set[str]:
        if self.database is None:
            return set()
        with self.database.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position;",
                (table_name,),
            )
            return {row[0] for row in cursor.fetchall()}

    def _validate_columns(self, table_name: str, columns: Optional[List[str]]) -> List[str]:
        if columns is None:
            return []
        if not isinstance(columns, list):
            raise ValueError("Columns must be a list of strings.")
        if not columns:
            return []
        available_columns = self._get_schema_columns(table_name)
        validated: List[str] = []
        for column in columns:
            if not column or not isinstance(column, str):
                raise ValueError("Each column must be a non-empty string.")
            if self._is_sensitive_column(column):
                raise ValueError(f"Sensitive column '{column}' is not allowed.")
            if column not in available_columns:
                raise ValueError(f"Column '{column}' is not in table '{table_name}'.")
            validated.append(self._quote_identifier(column))
        return validated

    def _validate_where(self, table_name: str, where: Optional[Dict[str, Any]]) -> tuple[List[str], List[Any]]:
        if where is None:
            return [], []
        if not isinstance(where, dict):
            raise ValueError("WHERE filters must be an object.")

        available_columns = self._get_schema_columns(table_name)
        clauses: List[str] = []
        values: List[Any] = []
        for key, value in where.items():
            if not key or not isinstance(key, str):
                raise ValueError("Filter keys must be non-empty strings.")
            if self._is_sensitive_column(key):
                raise ValueError(f"Sensitive column '{key}' is not allowed in filters.")
            if key not in available_columns:
                raise ValueError(f"Filter column '{key}' is not in table '{table_name}'.")
            if self._is_sql_injection_candidate(value):
                raise ValueError(f"Invalid value for filter column '{key}'.")
            clauses.append(f"{self._quote_identifier(key)} = %s")
            values.append(value)
        return clauses, values

    def _execute_read_query(self, query: str, params: Optional[List[Any]] = None) -> Any:
        if self.database is None:
            raise ConnectionError("Database connection is not available.")
        try:
            with self.database.cursor() as cursor:
                # Use session-level timeout so this works with autocommit / poolers.
                cursor.execute(f"SET statement_timeout = {int(self.query_timeout_ms)}")
                cursor.execute(query, params or [])
                return cursor.fetchall()
        except TimeoutError as exc:
            raise TimeoutError(f"Query timed out after {self.query_timeout_ms} ms.") from exc
        except Exception:
            # Clear aborted-transaction state on non-autocommit connections.
            try:
                self.database.rollback()
            except Exception:
                pass
            raise

    def count_records(self, table_name: str, where: Optional[Dict[str, Any]] = None) -> int:
        table = self._validate_table(table_name)
        clauses, values = self._validate_where(table_name, where)
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT COUNT(*) FROM {table}{where_clause};"
        rows = self._execute_read_query(query, values)
        return int(rows[0][0]) if rows else 0

    def find_records(self, table_name: str, columns: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        table = self._validate_table(table_name)
        selected_columns = self._validate_columns(table_name, columns)
        if not selected_columns:
            selected_columns = [self._quote_identifier(col) for col in self._get_schema_columns(table_name) if not self._is_sensitive_column(col)]
        if limit is None:
            limit = min(self.max_records, 50)
        if limit < 1 or limit > self.max_records:
            raise ValueError(f"Limit must be between 1 and {self.max_records}.")
        if offset < 0:
            raise ValueError("Offset must be >= 0.")

        clauses, values = self._validate_where(table_name, where)
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT {', '.join(selected_columns)} FROM {table}{where_clause} LIMIT %s OFFSET %s;"
        params = values + [limit, offset]
        rows = self._execute_read_query(query, params)
        return [dict(zip([col.strip('"') for col in selected_columns], row)) for row in rows]

    def aggregate_data(self, table_name: str, operation: str, column: Optional[str] = None, group_by: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        table = self._validate_table(table_name)
        allowed_operations = {"count", "sum", "avg", "min", "max"}
        operation_name = str(operation).lower()
        if operation_name not in allowed_operations:
            raise ValueError("Only COUNT, SUM, AVG, MIN, and MAX are allowed.")
        if operation_name == "count":
            aggregate_expression = "COUNT(*)"
        else:
            if not column or not isinstance(column, str):
                raise ValueError(f"Column is required for {operation_name.upper()}.")
            if self._is_sensitive_column(column):
                raise ValueError(f"Sensitive column '{column}' is not allowed.")
            available_columns = self._get_schema_columns(table_name)
            if column not in available_columns:
                raise ValueError(f"Column '{column}' is not in table '{table_name}'.")
            aggregate_expression = f"{operation_name.upper()}({self._quote_identifier(column)})"

        group_columns: List[str] = []
        if group_by:
            if not isinstance(group_by, list):
                raise ValueError("group_by must be a list of column names.")
            for group_column in group_by:
                if self._is_sensitive_column(group_column):
                    raise ValueError(f"Sensitive column '{group_column}' is not allowed in GROUP BY.")
                if group_column not in self._get_schema_columns(table_name):
                    raise ValueError(f"Group by column '{group_column}' is not in table '{table_name}'.")
                group_columns.append(self._quote_identifier(group_column))

        clauses, values = self._validate_where(table_name, where)
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        if group_columns:
            query = f"SELECT {', '.join(group_columns)}, {aggregate_expression} FROM {table}{where_clause} GROUP BY {', '.join(group_columns)};"
        else:
            query = f"SELECT {aggregate_expression} FROM {table}{where_clause};"
        rows = self._execute_read_query(query, values)
        result: List[Dict[str, Any]] = []
        if group_columns:
            for row in rows:
                item = {group_columns[i].strip('"'): row[i] for i in range(len(group_columns))}
                item[operation_name.upper()] = row[-1]
                result.append(item)
        else:
            result.append({operation_name.upper(): rows[0][0]})
        return result

    def reject_write_operation(self, operation_name: str) -> None:
        if operation_name.lower() in {"insert", "update", "delete", "drop", "alter", "create", "truncate", "rename"}:
            raise ValueError(f"Write operation '{operation_name}' is not allowed.")
