from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, field_validator

from .schema_catalog import SchemaCatalog


class JoinSpec(BaseModel):
    left_table: str
    left_column: str
    right_table: str
    right_column: str


class SelectExpr(BaseModel):
    expr_type: str = Field(..., description="column | aggregate | calc")
    table: Optional[str] = None
    column: Optional[str] = None
    operation: Optional[str] = None
    alias: str
    filter_column: Optional[str] = None
    filter_value: Optional[str] = None


class OrderBySpec(BaseModel):
    alias_or_column: str
    direction: str = "ASC"


class FilterSpec(BaseModel):
    table: str
    column: str
    operator: str = "="
    value: Any = None


class QueryPlan(BaseModel):
    tool: str = Field(default="run_sql_plan")
    intent: str = "query"
    tables: List[str] = Field(default_factory=list)
    joins: List[JoinSpec] = Field(default_factory=list)
    select: List[SelectExpr] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    filters: List[FilterSpec] = Field(default_factory=list)
    order_by: List[OrderBySpec] = Field(default_factory=list)
    limit: Optional[int] = None
    # Multi-query calculation: e.g. revenue - expenses
    calculation: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    # Backward-compatible fields used by older UI/tests
    table: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    aggregation: Optional[Dict[str, Any]] = None

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, value: str) -> str:
        allowed = {"run_sql_plan", "count_records", "find_records", "aggregate_data", "unsupported"}
        if value not in allowed:
            raise ValueError("Unsupported query tool.")
        return value


class QueryPlanner:
    """Schema-aware, rule-based planner (no external LLM)."""

    ENTITY_KEYWORDS: Dict[str, List[str]] = {
        "companies": ["company", "companies", "business", "organization", "organisation", "firm"],
        "customers": ["customer", "customers", "client", "clients"],
        "employees": ["employee", "employees", "staff", "worker", "workers", "salary", "salaries"],
        "departments": ["department", "departments"],
        "products": ["product", "products"],
        "projects": ["project", "projects"],
        "invoices": ["invoice", "invoices"],
        "expenses": ["expense", "expenses"],
        "revenues": ["revenue", "revenues"],
        "orders": ["order", "orders", "sale", "sales"],
        "users": ["user", "users", "registered user", "registered users"],
    }

    ILLEGAL_PATTERNS = [
        "drop table",
        "delete ",
        "update ",
        "insert into",
        "truncate",
        "alter table",
        "create table",
        "password",
        "run this sql",
        ";--",
    ]

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text).lower()).strip()

    @classmethod
    def _is_illegal(cls, text: str) -> bool:
        return any(pattern in text for pattern in cls.ILLEGAL_PATTERNS)

    @classmethod
    def _detect_tables(cls, text: str, available: Set[str]) -> List[str]:
        scored: List[Tuple[int, str]] = []
        for table, keywords in cls.ENTITY_KEYWORDS.items():
            if table not in available:
                continue
            for keyword in keywords:
                if keyword in text:
                    scored.append((len(keyword), table))
        # Prefer unique tables sorted by keyword strength.
        ordered: List[str] = []
        for _, table in sorted(scored, reverse=True):
            if table not in ordered:
                ordered.append(table)
        # Schema-driven fallback: match table names directly.
        for table in sorted(available):
            singular = table[:-1] if table.endswith("s") else table
            if table in text or singular in text:
                if table not in ordered:
                    ordered.append(table)
        return ordered

    @classmethod
    def _metric_table(cls, text: str, available: Set[str], catalog: SchemaCatalog) -> Optional[str]:
        if "revenue" in text and "revenues" in available:
            return "revenues"
        if "expense" in text and "expenses" in available:
            return "expenses"
        if "salary" in text or "salaries" in text:
            if "employees" in available:
                return "employees"
        if "order" in text and "orders" in available:
            return "orders"
        if "invoice" in text and "invoices" in available:
            return "invoices"
        detected = cls._detect_tables(text, available)
        for table in detected:
            if catalog.find_amount_column(table):
                return table
        return detected[0] if detected else None

    @classmethod
    def _direct_fk(cls, catalog: SchemaCatalog, left: str, right: str) -> Optional[JoinSpec]:
        for fk in catalog.foreign_keys:
            if fk.table == left and fk.ref_table == right:
                return JoinSpec(
                    left_table=fk.table,
                    left_column=fk.column,
                    right_table=fk.ref_table,
                    right_column=fk.ref_column,
                )
            if fk.table == right and fk.ref_table == left:
                return JoinSpec(
                    left_table=fk.table,
                    left_column=fk.column,
                    right_table=fk.ref_table,
                    right_column=fk.ref_column,
                )
        return None

    @classmethod
    def _build_joins(cls, catalog: SchemaCatalog, tables: List[str]) -> Tuple[List[JoinSpec], Optional[str]]:
        if len(tables) <= 1:
            return [], None

        # Prefer direct FK between first two tables (common Q&A pattern).
        if len(tables) == 2:
            direct = cls._direct_fk(catalog, tables[0], tables[1])
            if direct is not None:
                return [direct], None

        joins: List[JoinSpec] = []
        connected = {tables[0]}
        for table in tables[1:]:
            attached = False
            for start in list(connected):
                direct = cls._direct_fk(catalog, start, table)
                if direct is not None:
                    joins.append(direct)
                    connected.add(table)
                    attached = True
                    break
                path = catalog.join_path(start, table)
                if path:
                    for edge in path:
                        joins.append(
                            JoinSpec(
                                left_table=edge.table,
                                left_column=edge.column,
                                right_table=edge.ref_table,
                                right_column=edge.ref_column,
                            )
                        )
                        connected.add(edge.table)
                        connected.add(edge.ref_table)
                    connected.add(table)
                    attached = True
                    break
            if not attached:
                return [], f"I could not find a safe join path between {sorted(connected)} and '{table}' in the schema."

        unique: List[JoinSpec] = []
        seen = set()
        for join in joins:
            key = (join.left_table, join.left_column, join.right_table, join.right_column)
            if key in seen:
                continue
            seen.add(key)
            unique.append(join)
        return unique, None

    @classmethod
    def _compat_fields(cls, plan: QueryPlan) -> QueryPlan:
        plan.table = plan.tables[0] if plan.tables else None
        plan.columns = [expr.alias for expr in plan.select]
        if plan.select and plan.select[0].expr_type == "aggregate":
            plan.aggregation = {
                "operation": plan.select[0].operation,
                "column": plan.select[0].column,
            }
        return plan

    @classmethod
    def unsupported(cls, reason: str) -> QueryPlan:
        return QueryPlan(tool="unsupported", intent="unsupported", reason=reason)

    @classmethod
    def build_plan(cls, message: str, catalog: SchemaCatalog, available_tables: Optional[Set[str]] = None) -> QueryPlan:
        if not message or not str(message).strip():
            return cls.unsupported("The question was empty.")

        text = cls._normalize(message)
        if cls._is_illegal(text):
            return cls.unsupported("That request looks unsafe or asks for restricted information.")

        available = set(available_tables or catalog.table_names())
        if not available:
            return cls.unsupported("No tables are available in the connected database.")

        # 1) Comparison / calculation across metrics
        if ("revenue" in text and "expense" in text) and any(token in text for token in ("minus", "compare", "difference", "vs", "versus", "-")):
            if "revenues" not in available or "expenses" not in available:
                return cls.unsupported("Revenue/expense comparison needs both 'revenues' and 'expenses' tables.")
            rev_col = catalog.find_amount_column("revenues")
            exp_col = catalog.find_amount_column("expenses")
            if not rev_col or not exp_col:
                return cls.unsupported("Could not find numeric amount columns for revenue and expenses.")
            plan = QueryPlan(
                tool="run_sql_plan",
                intent="calculation",
                tables=["revenues", "expenses"],
                calculation={
                    "operation": "subtract",
                    "left": {"table": "revenues", "operation": "SUM", "column": rev_col, "alias": "total_revenue"},
                    "right": {"table": "expenses", "operation": "SUM", "column": exp_col, "alias": "total_expenses"},
                    "alias": "revenue_minus_expenses",
                },
                select=[
                    SelectExpr(expr_type="calc", alias="total_revenue"),
                    SelectExpr(expr_type="calc", alias="total_expenses"),
                    SelectExpr(expr_type="calc", alias="revenue_minus_expenses"),
                ],
            )
            return cls._compat_fields(plan)

        # 2) Percentage questions
        if "percent" in text or "percentage" in text:
            table = "employees" if "employee" in text and "employees" in available else cls._metric_table(text, available, catalog)
            if not table:
                return cls.unsupported("I could not determine which table to use for the percentage calculation.")
            status_col = catalog.find_status_column(table)
            if not status_col:
                return cls.unsupported(f"Table '{table}' has no status column for percentage calculations.")
            value = "Active" if "active" in text else None
            if value is None:
                return cls.unsupported("Specify which status to use for the percentage (for example, active).")
            plan = QueryPlan(
                tool="run_sql_plan",
                intent="percentage",
                tables=[table],
                select=[
                    SelectExpr(
                        expr_type="aggregate",
                        table=table,
                        column="*",
                        operation="PERCENT",
                        alias="percentage",
                        filter_column=status_col,
                        filter_value=value,
                    )
                ],
                table=table,
            )
            return cls._compat_fields(plan)

        # 3) Grouped counts: employees in each department
        if any(token in text for token in ("each", "per ", "by ", "group")) or (
            "number of" in text and "department" in text
        ):
            measure_table = None
            group_table = None
            if "employee" in text and "department" in text:
                measure_table, group_table = "employees", "departments"
            elif "order" in text and "customer" in text:
                measure_table, group_table = "orders", "customers"
            elif "expense" in text and "department" in text:
                measure_table, group_table = "expenses", "departments"
            else:
                detected = cls._detect_tables(text, available)
                if len(detected) >= 2:
                    measure_table, group_table = detected[0], detected[1]
                elif len(detected) == 1:
                    measure_table = detected[0]

            if measure_table and group_table and measure_table in available and group_table in available:
                joins, join_error = cls._build_joins(catalog, [measure_table, group_table])
                if join_error:
                    return cls.unsupported(join_error)
                name_col = catalog.find_name_column(group_table) or catalog.safe_columns(group_table)[0]
                amount_col = catalog.find_amount_column(measure_table)
                if "expense" in text or "revenue" in text or "salary" in text or "total" in text or "sum" in text:
                    if not amount_col:
                        return cls.unsupported(f"No numeric column found on '{measure_table}' for aggregation.")
                    operation = "SUM"
                    alias = f"total_{amount_col}"
                    select_col = amount_col
                else:
                    operation = "COUNT"
                    alias = "count"
                    select_col = "*"
                order_dir = "DESC" if any(token in text for token in ("highest", "most", "top", "largest")) else "ASC"
                limit = 1 if any(token in text for token in ("highest", "most", "which", "top")) else None
                plan = QueryPlan(
                    tool="run_sql_plan",
                    intent="group_aggregate",
                    tables=[measure_table, group_table],
                    joins=joins,
                    select=[
                        SelectExpr(expr_type="column", table=group_table, column=name_col, alias=name_col),
                        SelectExpr(
                            expr_type="aggregate",
                            table=measure_table,
                            column=select_col,
                            operation=operation,
                            alias=alias,
                        ),
                    ],
                    group_by=[f"{group_table}.{name_col}"],
                    order_by=[OrderBySpec(alias_or_column=alias, direction=order_dir)],
                    limit=limit,
                )
                return cls._compat_fields(plan)

        # 3.5) Single-table ranking: highest/lowest salary, highest budget, etc.
        if any(token in text for token in ("highest", "lowest", "most", "least", "top", "bottom")):
            single_table = None
            metric_col = None
            direction = "DESC" if any(token in text for token in ("highest", "most", "top")) else "ASC"

            if "salary" in text and "employees" in available:
                single_table = "employees"
                metric_col = "salary"
            elif "budget" in text and "departments" in available:
                single_table = "departments"
                metric_col = "budget"

            if single_table and metric_col:
                name_cols: List[str] = []
                name_col = catalog.find_name_column(single_table)
                if name_col:
                    if "," in name_col:
                        name_cols = [part.strip() for part in name_col.split(",")]
                    else:
                        name_cols = [name_col]
                if single_table == "employees" and "first_name" not in name_cols:
                    if catalog.has_column("employees", "first_name"):
                        name_cols.insert(0, "first_name")
                if single_table == "employees" and "last_name" not in name_cols:
                    if catalog.has_column("employees", "last_name"):
                        name_cols.append("last_name")

                select_exprs = [
                    SelectExpr(expr_type="column", table=single_table, column=col, alias=col)
                    for col in name_cols
                ]
                select_exprs.append(
                    SelectExpr(expr_type="column", table=single_table, column=metric_col, alias=metric_col)
                )

                plan = QueryPlan(
                    tool="run_sql_plan",
                    intent="top_group",
                    tables=[single_table],
                    select=select_exprs,
                    order_by=[OrderBySpec(alias_or_column=metric_col, direction=direction)],
                    limit=100,
                )
                return cls._compat_fields(plan)

        # 4) Which X has the most/highest Y
        if text.startswith("which") or "highest" in text or "most" in text or "lowest" in text or "least" in text:
            detected = cls._detect_tables(text, available)
            if "department" in text and "employee" in text:
                measure_table, group_table = "employees", "departments"
            elif "customer" in text and "order" in text:
                measure_table, group_table = "orders", "customers"
            elif "department" in text and "expense" in text:
                measure_table, group_table = "expenses", "departments"
            elif "company" in text and "revenue" in text:
                measure_table, group_table = "revenues", "companies"
            elif "company" in text and "expense" in text:
                measure_table, group_table = "expenses", "companies"
            elif len(detected) >= 2:
                measure_table, group_table = detected[0], detected[1]
                # Prefer fact table first for measure.
                if measure_table in {"departments", "customers", "companies", "employees"} and group_table in {
                    "expenses",
                    "orders",
                    "revenues",
                    "invoices",
                }:
                    measure_table, group_table = group_table, measure_table
            else:
                return cls.unsupported("I could not determine which tables to compare for this ranking question.")

            if measure_table not in available or group_table not in available:
                return cls.unsupported("Required tables for this ranking question are not available.")
            joins, join_error = cls._build_joins(catalog, [measure_table, group_table])
            if join_error:
                return cls.unsupported(join_error)
            name_col = catalog.find_name_column(group_table)
            amount_col = catalog.find_amount_column(measure_table)
            if not name_col:
                return cls.unsupported(f"Could not find a name column on '{group_table}'.")
            metric_indicators = (
                "expense",
                "revenue",
                "salary",
                "budget",
                "amount",
                "total",
                "sum",
                "avg",
                "average",
                "cost",
                "price",
                "unit_price",
            )
            count_indicators = (
                "employee",
                "employees",
                "customer",
                "customers",
                "order",
                "orders",
                "invoice",
                "invoices",
                "project",
                "projects",
            )
            use_count = False
            if "order" in text and "most" in text and "expense" not in text and "revenue" not in text:
                use_count = True
            elif any(token in text for token in count_indicators) and not any(token in text for token in metric_indicators):
                use_count = True

            if use_count:
                operation, select_col, alias = "COUNT", "*", "count"
            else:
                if not amount_col:
                    return cls.unsupported(f"No numeric column found on '{measure_table}'.")
                operation, select_col, alias = "SUM", amount_col, f"total_{amount_col}"
            direction = "ASC" if any(token in text for token in ("lowest", "least", "smallest")) else "DESC"
            plan = QueryPlan(
                tool="run_sql_plan",
                intent="top_group",
                tables=[measure_table, group_table],
                joins=joins,
                select=[
                    SelectExpr(expr_type="column", table=group_table, column=name_col, alias=name_col),
                    SelectExpr(
                        expr_type="aggregate",
                        table=measure_table,
                        column=select_col,
                        operation=operation,
                        alias=alias,
                    ),
                ],
                group_by=[f"{group_table}.{name_col}"],
                order_by=[OrderBySpec(alias_or_column=alias, direction=direction)],
            )
            return cls._compat_fields(plan)

        # 5) Simple aggregates: total / average / min / max
        if any(token in text for token in ("total", "sum", "average", "avg", "minimum", "maximum", "min ", "max ")):
            table = cls._metric_table(text, available, catalog)
            if not table:
                return cls.unsupported("I could not determine which table contains the requested metric.")
            column = catalog.find_amount_column(table)
            if "salary" in text and catalog.has_column(table, "salary"):
                column = "salary"
            if not column:
                return cls.unsupported(f"No numeric metric column was found on table '{table}'.")
            if "average" in text or "avg" in text:
                operation = "AVG"
            elif "maximum" in text or re.search(r"\bmax\b", text):
                operation = "MAX"
            elif "minimum" in text or re.search(r"\bmin\b", text):
                operation = "MIN"
            else:
                operation = "SUM"
            alias = f"{operation.lower()}_{column}"
            plan = QueryPlan(
                tool="run_sql_plan",
                intent="aggregate",
                tables=[table],
                select=[SelectExpr(expr_type="aggregate", table=table, column=column, operation=operation, alias=alias)],
            )
            return cls._compat_fields(plan)

        # 6) Counts
        if any(token in text for token in ("how many", "count", "number of")):
            detected = cls._detect_tables(text, available)
            table = detected[0] if detected else None
            if not table:
                return cls.unsupported("I could not determine which table to count.")
            filters: List[FilterSpec] = []
            status_col = catalog.find_status_column(table)
            if status_col and "active" in text:
                filters.append(FilterSpec(table=table, column=status_col, operator="=", value="Active"))
            plan = QueryPlan(
                tool="run_sql_plan",
                intent="count",
                tables=[table],
                select=[SelectExpr(expr_type="aggregate", table=table, column="*", operation="COUNT", alias="count")],
                filters=filters,
            )
            return cls._compat_fields(plan)

        # 7) Name / find / list questions
        detected = cls._detect_tables(text, available)
        table = detected[0] if detected else None
        if table is None:
            return cls.unsupported(
                "I could not map that question to any table in the connected schema. "
                f"Available tables include: {', '.join(sorted(available))}."
            )

        name_col = catalog.find_name_column(table)
        columns = catalog.safe_columns(table)[:6]
        if any(token in text for token in ("name", "called")) and name_col:
            columns = [name_col]
        elif name_col and name_col not in columns:
            columns = [name_col] + columns
        limit = 1 if any(token in text for token in ("name", "which", "who")) else 10
        match = re.search(r"\b(\d+)\b", text)
        if match:
            limit = min(int(match.group(1)), 50)

        filters: List[FilterSpec] = []
        status_col = catalog.find_status_column(table)
        if status_col and "active" in text:
            filters.append(FilterSpec(table=table, column=status_col, operator="=", value="Active"))

        plan = QueryPlan(
            tool="run_sql_plan",
            intent="find",
            tables=[table],
            select=[SelectExpr(expr_type="column", table=table, column=col, alias=col) for col in columns],
            filters=filters,
            limit=limit,
        )
        return cls._compat_fields(plan)
