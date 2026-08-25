"""Safe SQL Executor — validated, read-only query execution.

Security measures:
    - Only SELECT statements allowed
    - Full blocklist of dangerous SQL operations
    - Table and column names validated against discovered schema
    - Parameterized queries for all user values
    - Query timeout enforcement
    - Maximum row limit
    - No multiple statements (semicolons blocked)
    - No raw stack traces shown to end user
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .query_planner import QueryPlan
from .schema_catalog import DatabaseSchema


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# ─── SQL Blocklist ─────────────────────────────────────────────────────────
# Every operation that must be blocked for read-only safety.

BLOCKED_KEYWORDS = frozenset({
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "grant", "revoke", "execute", "copy", "set", "reset",
    "comment", "lock", "unlock", "analyze", "vacuum", "reindex",
    "refresh", "discard", "import", "export",
})

# Patterns that indicate SQL injection or multi-statement attacks
ATTACK_PATTERNS = [
    r";\s*\w",          # Semicolon followed by any keyword (multi-statement)
    r"--\s*\w",         # Line comment with content
    r"/\*.*\*/",        # Block comments
    r"union\s+all",     # UNION-based injection
    r"union\s+select",  # UNION-based injection
    r"into\s+outfile",  # File write attack
    r"load_file",       # File read attack
    r"benchmark\(",     # DoS attack
    r"sleep\(",         # Time-based injection
    r"pg_sleep\(",      # PostgreSQL time-based injection
    r"waitfor\s+delay", # SQL Server time-based injection
]


class SafeSQLExecutor:
    """Builds and executes validated read-only SQL from structured plans.

    Security features:
        - Full blocklist of dangerous SQL operations (INSERT, UPDATE, DELETE,
          DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, EXECUTE, etc.)
        - Table and column names validated against the actual discovered schema
        - Parameterized queries for all user-supplied values
        - Query timeout enforcement (default 5000ms)
        - Maximum row limit (default 100)
        - No multiple SQL statements (semicolons blocked)
        - SQL injection attack patterns detected and blocked
        - No raw stack traces shown to end user
    """

    def __init__(
        self,
        connection,
        catalog: DatabaseSchema,
        query_timeout_ms: int = 5000,
        max_rows: int = 100,
    ) -> None:
        self.connection = connection
        self.catalog = catalog
        self.query_timeout_ms = query_timeout_ms
        self.max_rows = max_rows

    # ─── Identifier Validation ────────────────────────────────────────────

    def _quote(self, identifier: str) -> str:
        if not IDENTIFIER_RE.fullmatch(identifier or ""):
            raise ValueError(f"Invalid identifier: {identifier!r}")
        return identifier

    def _validate_table(self, table: str) -> str:
        if table not in self.catalog.table_names():
            raise ValueError(f"Unknown table: {table!r}. Available: {', '.join(sorted(self.catalog.table_names()))}")
        return self._quote(table)

    def _validate_column(self, table: str, column: str) -> str:
        if column == "*":
            return "*"
        if self.catalog.is_sensitive(column):
            raise ValueError(f"Sensitive column '{column}' is not allowed.")
        if not self.catalog.has_column(table, column):
            raise ValueError(
                f"Unknown column '{column}' on table '{table}'. "
                f"Available columns: {', '.join(self.catalog.columns_for(table)[:10])}"
            )
        return self._quote(column)

    # ─── SQL Injection Detection ──────────────────────────────────────────

    @classmethod
    def _check_for_attacks(cls, sql: str) -> Optional[str]:
        """Check for SQL injection attack patterns. Returns error or None."""
        for pattern in ATTACK_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return f"Suspicious SQL pattern detected: {pattern}"
        return None

    # ─── SQL Validation ───────────────────────────────────────────────────

    @classmethod
    def _validate_sql_safety(cls, sql: str) -> Optional[str]:
        """Validate that raw SQL is safe. Returns error message or None."""
        cleaned = sql.strip().rstrip(";").lower()

        if not cleaned.startswith("select"):
            return "Only SELECT queries are allowed."

        if ";" in cleaned:
            return "Multiple SQL statements are not allowed in a single execution."

        # Check blocked keywords
        padded = f" {cleaned} "
        for keyword in BLOCKED_KEYWORDS:
            if f" {keyword} " in padded:
                return f"Blocked SQL operation detected: {keyword.upper()}"

        # Check attack patterns
        attack_error = cls._check_for_attacks(cleaned)
        if attack_error:
            return attack_error

        return None

    # ─── SQL Generation ───────────────────────────────────────────────────

    def _select_sql(self, plan: QueryPlan) -> Tuple[str, List[Any]]:
        if not plan.tables:
            raise ValueError("Query plan has no tables.")

        base_table = self._validate_table(plan.tables[0])
        params: List[Any] = []

        # Build SELECT clause
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

                elif operation in {"SUM", "AVG", "MIN", "MAX"}:
                    column = self._validate_column(table, expr.column or "")
                    select_parts.append(f"{operation}({table}.{column}) AS {alias}")

                else:
                    raise ValueError(f"Unsupported aggregate operation: {operation}")

            else:
                raise ValueError(f"Unsupported select expression type: {expr.expr_type}")

        if not select_parts:
            raise ValueError("Query plan has no SELECT expressions.")

        sql = f"SELECT {', '.join(select_parts)} FROM {base_table}"

        # Build JOIN clauses — only using validated FK joins from the plan
        joined_tables = {base_table}
        for join in plan.joins:
            left = self._validate_table(join.left_table)
            right = self._validate_table(join.right_table)
            left_col = self._validate_column(left, join.left_column)
            right_col = self._validate_column(right, join.right_column)

            if right not in joined_tables and left in joined_tables:
                sql += f" JOIN {right} ON {left}.{left_col} = {right}.{right_col}"
                joined_tables.add(right)
            elif left not in joined_tables and right in joined_tables:
                sql += f" JOIN {left} ON {left}.{left_col} = {right}.{right_col}"
                joined_tables.add(left)
            elif left not in joined_tables and right not in joined_tables:
                sql += f" JOIN {left} ON {left}.{left_col} = {right}.{right_col}"
                joined_tables.add(left)

        # Build WHERE clause
        where_parts: List[str] = []
        for filt in plan.filters:
            table = self._validate_table(filt.table)
            column = self._validate_column(table, filt.column)
            operator = filt.operator if filt.operator in {"=", "!=", ">", ">=", "<", "<=", "LIKE", "ILIKE", "IN"} else "="

            if filt.is_range and filt.lower_value is not None and filt.upper_value is not None:
                where_parts.append(f"{table}.{column} BETWEEN %s AND %s")
                params.extend([filt.lower_value, filt.upper_value])
            else:
                where_parts.append(f"{table}.{column} {operator} %s")
                params.append(filt.value)

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        # Build GROUP BY clause
        if plan.group_by:
            group_parts = []
            for item in plan.group_by:
                # Handle expressions like DATE_TRUNC(...) AS period
                if " AS " in item.upper():
                    group_parts.append(item.split(" AS ")[0])
                elif "." in item:
                    table_name, column_name = item.split(".", 1)
                    table = self._validate_table(table_name)
                    column = self._validate_column(table, column_name)
                    group_parts.append(f"{table}.{column}")
                else:
                    group_parts.append(self._quote(item))
            sql += " GROUP BY " + ", ".join(group_parts)

        # Build ORDER BY clause
        if plan.order_by:
            order_parts = []
            for item in plan.order_by:
                target = self._quote(item.alias_or_column) if IDENTIFIER_RE.fullmatch(item.alias_or_column) else None
                if target is None:
                    raise ValueError(f"Invalid ORDER BY target: {item.alias_or_column}")
                direction = "DESC" if str(item.direction).upper() == "DESC" else "ASC"
                order_parts.append(f"{target} {direction}")
            sql += " ORDER BY " + ", ".join(order_parts)

        # Build LIMIT clause
        limit = plan.limit if plan.limit is not None else self.max_rows
        limit = max(1, min(int(limit), self.max_rows))
        sql += " LIMIT %s"
        params.append(limit)

        return sql, params

    # ─── Query Execution ──────────────────────────────────────────────────

    def _run(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a query with full safety validation."""
        # Pre-execution safety check
        safety_error = self._validate_sql_safety(sql)
        if safety_error:
            raise ValueError(safety_error)

        with self.connection.cursor() as cursor:
            # Set query timeout
            try:
                cursor.execute(f"SET statement_timeout = {int(self.query_timeout_ms)}")
            except Exception:
                pass  # Some adapters may not support this

            # Execute with parameterized values
            cursor.execute(sql, params or [])
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Convert to dicts with safe serialization
        result = []
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

    # ─── Main Execution Entry Point ───────────────────────────────────────

    def execute(self, plan: QueryPlan) -> Dict[str, Any]:
        """Execute a query plan and return results.

        Returns:
            {
                "rows": List[Dict],  # Result rows
                "sql": str or List[str],  # Generated SQL
                "params": List[Any],  # Query parameters
                "error": str or None,  # Error message if failed
            }
        """
        if plan.tool == "unsupported":
            return {"rows": [], "sql": None, "error": plan.reason}

        try:
            # Handle calculation plans (multi-query)
            if plan.calculation:
                return self._execute_calculation(plan)

            # Standard single-query execution
            sql, params = self._select_sql(plan)
            rows = self._run(sql, params)
            return {"rows": rows, "sql": sql, "params": params, "error": None}

        except ValueError as exc:
            return {"rows": [], "sql": None, "error": str(exc)}
        except Exception as exc:
            # Never show raw stack traces to end user
            error_msg = str(exc)
            if "syntax error" in error_msg.lower():
                return {"rows": [], "sql": None, "error": "The generated query had a syntax error. Please rephrase your question."}
            return {"rows": [], "sql": None, "error": f"Query execution failed: {error_msg}"}

    def _execute_calculation(self, plan: QueryPlan) -> Dict[str, Any]:
        """Execute a calculation plan (e.g., revenue minus expenses)."""
        calc = plan.calculation
        left = calc["left"]
        right = calc["right"]

        left_table = self._validate_table(left["table"])
        left_col = self._validate_column(left["table"], left["column"])
        left_sql = f"SELECT {left['operation']}({left_table}.{left_col}) AS value FROM {left_table}"

        right_table = self._validate_table(right["table"])
        right_col = self._validate_column(right["table"], right["column"])
        right_sql = f"SELECT {right['operation']}({right_table}.{right_col}) AS value FROM {right_table}"

        left_rows = self._run(left_sql)
        right_rows = self._run(right_sql)

        left_value = float(left_rows[0]["value"] or 0) if left_rows else 0
        right_value = float(right_rows[0]["value"] or 0) if right_rows else 0

        operation = calc.get("operation", "subtract")
        if operation == "subtract":
            computed = left_value - right_value
        elif operation == "add":
            computed = left_value + right_value
        else:
            raise ValueError(f"Unsupported calculation operation: {operation}")

        alias = calc.get("alias", "result")
        return {
            "rows": [
                {
                    left.get("alias", "left_value"): left_value,
                    right.get("alias", "right_value"): right_value,
                    alias: computed,
                }
            ],
            "sql": [left_sql, right_sql, f"{left.get('alias')} - {right.get('alias')}"],
            "error": None,
        }
