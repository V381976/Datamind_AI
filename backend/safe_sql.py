from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .query_planner import QueryPlan
from .schema_catalog import SchemaCatalog


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SafeSQLExecutor:
    """Builds and executes validated read-only SQL from structured plans."""

    def __init__(self, connection, catalog: SchemaCatalog, query_timeout_ms: int = 5000, max_rows: int = 100) -> None:
        self.connection = connection
        self.catalog = catalog
        self.query_timeout_ms = query_timeout_ms
        self.max_rows = max_rows

    def _quote(self, identifier: str) -> str:
        if not IDENTIFIER_RE.fullmatch(identifier or ""):
            raise ValueError(f"Invalid identifier: {identifier!r}")
        return identifier

    def _validate_table(self, table: str) -> str:
        if table not in self.catalog.table_names():
            raise ValueError(f"Unknown table: {table}")
        return self._quote(table)

    def _validate_column(self, table: str, column: str) -> str:
        if column == "*":
            return "*"
        if self.catalog.is_sensitive(column):
            raise ValueError(f"Sensitive column '{column}' is not allowed.")
        if not self.catalog.has_column(table, column):
            raise ValueError(f"Unknown column '{column}' on table '{table}'.")
        return self._quote(column)

    def _select_sql(self, plan: QueryPlan) -> Tuple[str, List[Any]]:
        if not plan.tables:
            raise ValueError("Query plan has no tables.")
        base_table = self._validate_table(plan.tables[0])
        params: List[Any] = []

        select_parts: List[str] = []
        for expr in plan.select:
            alias = self._quote(expr.alias)
            if expr.expr_type == "column":
                table = self._validate_table(expr.table or plan.tables[0])
                column = self._validate_column(table, expr.column or "")
                select_parts.append(f"{table}.{column} AS {alias}")
            elif expr.expr_type == "aggregate":
                table = self._validate_table(expr.table or plan.tables[0])
                operation = (expr.operation or "COUNT").upper()
                if operation == "PERCENT":
                    status_col = self._validate_column(table, expr.filter_column or "")
                    select_parts.append(
                        "ROUND(100.0 * COUNT(*) FILTER (WHERE "
                        f"{table}.{status_col} = %s) / NULLIF(COUNT(*), 0), 2) AS {alias}"
                    )
                    params.append(expr.filter_value)
                elif operation == "COUNT":
                    if expr.column in (None, "*"):
                        select_parts.append(f"COUNT(*) AS {alias}")
                    else:
                        column = self._validate_column(table, expr.column)
                        select_parts.append(f"COUNT({table}.{column}) AS {alias}")
                else:
                    if operation not in {"SUM", "AVG", "MIN", "MAX"}:
                        raise ValueError(f"Unsupported aggregate: {operation}")
                    column = self._validate_column(table, expr.column or "")
                    select_parts.append(f"{operation}({table}.{column}) AS {alias}")
            else:
                raise ValueError(f"Unsupported select expression: {expr.expr_type}")

        sql = f"SELECT {', '.join(select_parts)} FROM {base_table}"

        joined_tables = {base_table}
        for join in plan.joins:
            left = self._validate_table(join.left_table)
            right = self._validate_table(join.right_table)
            left_col = self._validate_column(left, join.left_column)
            right_col = self._validate_column(right, join.right_column)
            # Join the table that is not yet in the FROM clause.
            if right not in joined_tables and left in joined_tables:
                sql += f" JOIN {right} ON {left}.{left_col} = {right}.{right_col}"
                joined_tables.add(right)
            elif left not in joined_tables and right in joined_tables:
                sql += f" JOIN {left} ON {left}.{left_col} = {right}.{right_col}"
                joined_tables.add(left)
            elif left not in joined_tables and right not in joined_tables:
                sql += f" JOIN {left} ON {left}.{left_col} = {right}.{right_col}"
                joined_tables.add(left)
                if right not in joined_tables:
                    # ensure both sides exist; if right missing, join it next loop
                    pass
            # else already joined

        where_parts: List[str] = []
        for filt in plan.filters:
            table = self._validate_table(filt.table)
            column = self._validate_column(table, filt.column)
            operator = filt.operator if filt.operator in {"=", "!=", ">", ">=", "<", "<="} else "="
            where_parts.append(f"{table}.{column} {operator} %s")
            params.append(filt.value)
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        if plan.group_by:
            group_parts = []
            for item in plan.group_by:
                if "." in item:
                    table_name, column_name = item.split(".", 1)
                    table = self._validate_table(table_name)
                    column = self._validate_column(table, column_name)
                    group_parts.append(f"{table}.{column}")
                else:
                    group_parts.append(self._quote(item))
            sql += " GROUP BY " + ", ".join(group_parts)

        if plan.order_by:
            order_parts = []
            for item in plan.order_by:
                target = self._quote(item.alias_or_column) if IDENTIFIER_RE.fullmatch(item.alias_or_column) else None
                if target is None:
                    raise ValueError(f"Invalid order by target: {item.alias_or_column}")
                direction = "DESC" if str(item.direction).upper() == "DESC" else "ASC"
                order_parts.append(f"{target} {direction}")
            sql += " ORDER BY " + ", ".join(order_parts)

        limit = plan.limit if plan.limit is not None else self.max_rows
        limit = max(1, min(int(limit), self.max_rows))
        sql += " LIMIT %s"
        params.append(limit)
        return sql, params

    def _run(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        cleaned = sql.strip().rstrip(";")
        lowered = cleaned.lower()
        if not lowered.startswith("select"):
            raise ValueError("Only SELECT queries are allowed.")
        if ";" in cleaned:
            raise ValueError("Unsafe SQL rejected.")
        forbidden = [" insert ", " update ", " delete ", " drop ", " alter ", " truncate ", " create "]
        padded = f" {lowered} "
        if any(token in padded for token in forbidden):
            raise ValueError("Unsafe SQL rejected.")
        with self.connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {int(self.query_timeout_ms)}")
            cursor.execute(sql, params or [])
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
        result = []
        for row in rows:
            item = {}
            for idx, column in enumerate(columns):
                value = row[idx]
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                elif type(value).__name__ == "Decimal":
                    value = float(value)
                item[column] = value
            result.append(item)
        return result

    def execute(self, plan: QueryPlan) -> Dict[str, Any]:
        if plan.tool == "unsupported":
            return {"rows": [], "sql": None, "error": plan.reason}

        if plan.calculation:
            left = plan.calculation["left"]
            right = plan.calculation["right"]
            left_sql = (
                f"SELECT {left['operation']}({self._validate_table(left['table'])}."
                f"{self._validate_column(left['table'], left['column'])}) AS value FROM {self._validate_table(left['table'])}"
            )
            right_sql = (
                f"SELECT {right['operation']}({self._validate_table(right['table'])}."
                f"{self._validate_column(right['table'], right['column'])}) AS value FROM {self._validate_table(right['table'])}"
            )
            left_rows = self._run(left_sql)
            right_rows = self._run(right_sql)
            left_value = left_rows[0]["value"] if left_rows else 0
            right_value = right_rows[0]["value"] if right_rows else 0
            if left_value is None:
                left_value = 0
            if right_value is None:
                right_value = 0
            operation = plan.calculation.get("operation", "subtract")
            if operation == "subtract":
                computed = float(left_value) - float(right_value)
            else:
                raise ValueError(f"Unsupported calculation: {operation}")
            alias = plan.calculation.get("alias", "result")
            return {
                "rows": [
                    {
                        left.get("alias", "left"): float(left_value),
                        right.get("alias", "right"): float(right_value),
                        alias: computed,
                    }
                ],
                "sql": [left_sql, right_sql, f"{left.get('alias')} - {right.get('alias')}"],
                "error": None,
            }

        sql, params = self._select_sql(plan)
        rows = self._run(sql, params)
        return {"rows": rows, "sql": sql, "params": params, "error": None}
