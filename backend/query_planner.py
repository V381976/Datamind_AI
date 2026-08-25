"""Universal Query Planner — schema-driven, fully generic.

Question classification categories:
    COUNT, AGGREGATION, RANKING, GROUPING, FILTERING,
    COMPARISON, TREND, TIME_BASED, DETAIL, ANALYSIS

Each question flows through:
    Question → Extract tokens → Match tables → Match columns →
    Discover FK joins → Determine intent → Build structured QueryPlan → Validate
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, field_validator

from .business_term_mapper import BusinessTermMapper
from .schema_catalog import DatabaseSchema


# ─── Intent Constants ──────────────────────────────────────────────────────

INTENT_COUNT = "count"
INTENT_AGGREGATION = "aggregation"
INTENT_RANKING = "ranking"
INTENT_GROUPING = "grouping"
INTENT_FILTERING = "filtering"
INTENT_COMPARISON = "comparison"
INTENT_TREND = "trend"
INTENT_TIME_BASED = "time_based"
INTENT_DETAIL = "detail"
INTENT_ANALYSIS = "analysis"
INTENT_UNSUPPORTED = "unsupported"

ALL_INTENTS = frozenset({
    INTENT_COUNT, INTENT_AGGREGATION, INTENT_RANKING, INTENT_GROUPING,
    INTENT_FILTERING, INTENT_COMPARISON, INTENT_TREND, INTENT_TIME_BASED,
    INTENT_DETAIL, INTENT_ANALYSIS, INTENT_UNSUPPORTED,
})


# ─── Plan Models ───────────────────────────────────────────────────────────

class JoinSpec(BaseModel):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    # Optional intermediate table for multi-hop joins
    intermediate_table: Optional[str] = None


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
    # For range filters
    lower_value: Optional[Any] = None
    upper_value: Optional[Any] = None
    is_range: bool = False


class TimeFilterSpec(BaseModel):
    """Time-based filter extracted from the question."""
    table: str
    column: str
    operator: str = ">="
    value: Optional[Any] = None
    # For BETWEEN
    lower_value: Optional[Any] = None
    upper_value: Optional[Any] = None
    is_between: bool = False


class QueryPlan(BaseModel):
    tool: str = Field(default="run_sql_plan")
    intent: str = "detail"
    tables: List[str] = Field(default_factory=list)
    joins: List[JoinSpec] = Field(default_factory=list)
    select: List[SelectExpr] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    filters: List[FilterSpec] = Field(default_factory=list)
    time_filters: List[TimeFilterSpec] = Field(default_factory=list)
    order_by: List[OrderBySpec] = Field(default_factory=list)
    limit: Optional[int] = None
    calculation: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    # Backward-compatible fields
    table: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    aggregation: Optional[Dict[str, Any]] = None

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, value: str) -> str:
        allowed = {"run_sql_plan", "count_records", "find_records",
                   "aggregate_data", "unsupported"}
        if value not in allowed:
            raise ValueError("Unsupported query tool.")
        return value


# ─── Query Planner ─────────────────────────────────────────────────────────

class QueryPlanner:
    """Schema-aware, rule-based planner — fully generic, no hardcoded tables.

    Intent classification handles 10 categories:
        COUNT, AGGREGATION, RANKING, GROUPING, FILTERING,
        COMPARISON, TREND, TIME_BASED, DETAIL, ANALYSIS
    """

    ILLEGAL_PATTERNS = [
        "drop table", "delete ", "update ", "insert into",
        "truncate", "alter table", "create table", "password",
        "run this sql", ";--", "grant ", "revoke ", "exec ",
        "execute ", "copy ", "set ", "reset ",
    ]

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text).lower()).strip()

    @classmethod
    def _is_illegal(cls, text: str) -> bool:
        return any(pattern in text for pattern in cls.ILLEGAL_PATTERNS)

    # ── Join discovery (FK-only) ──────────────────────────────────────────

    @classmethod
    def _direct_fk(cls, schema: DatabaseSchema, left: str, right: str) -> Optional[JoinSpec]:
        """Find a direct foreign key between two tables."""
        for fk in schema.foreign_keys:
            if fk.table == left and fk.ref_table == right:
                return JoinSpec(
                    left_table=fk.table, left_column=fk.column,
                    right_table=fk.ref_table, right_column=fk.ref_column,
                )
            if fk.table == right and fk.ref_table == left:
                return JoinSpec(
                    left_table=fk.table, left_column=fk.column,
                    right_table=fk.ref_table, right_column=fk.ref_column,
                )
        return None

    @classmethod
    def _build_joins(
        cls, schema: DatabaseSchema, tables: List[str]
    ) -> Tuple[List[JoinSpec], Optional[str]]:
        """Build joins using ONLY foreign keys. No cartesian joins allowed.

        Returns (joins, error_message). If error_message is set, the join
        path could not be safely determined.
        """
        if len(tables) <= 1:
            return [], None

        if len(tables) == 2:
            direct = cls._direct_fk(schema, tables[0], tables[1])
            if direct is not None:
                return [direct], None
            # Try multi-hop FK path
            path = schema.join_path(tables[0], tables[1])
            if path:
                joins = []
                for edge in path:
                    joins.append(
                        JoinSpec(
                            left_table=edge.table, left_column=edge.column,
                            right_table=edge.ref_table, right_column=edge.ref_column,
                        )
                    )
                return joins, None
            return [], (
                f"I found the tables '{tables[0]}' and '{tables[1]}', but I could not "
                f"safely determine how they are related. No foreign key path exists between them."
            )

        # Multi-table: BFS using only FK edges
        joins: List[JoinSpec] = []
        connected: Set[str] = {tables[0]}

        for table in tables[1:]:
            attached = False
            for start in list(connected):
                # Direct FK
                direct = cls._direct_fk(schema, start, table)
                if direct is not None:
                    joins.append(direct)
                    connected.add(table)
                    attached = True
                    break

                # Multi-hop via FK path
                path = schema.join_path(start, table)
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
                return [], (
                    f"I could not find a safe join path between {sorted(connected)} "
                    f"and '{table}'. No foreign key relationships connect them."
                )

        # Deduplicate
        unique: List[JoinSpec] = []
        seen: Set[Tuple[str, str, str, str]] = set()
        for join in joins:
            key = (join.left_table, join.left_column, join.right_table, join.right_column)
            if key not in seen:
                seen.add(key)
                unique.append(join)
        return unique, None

    # ── Backward-compat fields ────────────────────────────────────────────

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
        return QueryPlan(tool="unsupported", intent=INTENT_UNSUPPORTED, reason=reason)

    # ── Intent classification ─────────────────────────────────────────────

    @classmethod
    def _classify_intent(cls, text: str) -> str:
        """Classify the user's question into one of 10 intent categories."""
        # ORDER MATTERS: more specific patterns first.

        # TIME_BASED: mentions of time ranges or date filters
        time_signals = (
            "this month", "last month", "this year", "last year",
            "this week", "last week", "this quarter", "last quarter",
            "since ", "from ", "between", "before ", "after ",
            "in 2024", "in 2023", "in 2025",
        )
        if any(sig in text for sig in time_signals):
            return INTENT_TIME_BASED

        # TREND: wants to see change over time
        trend_signals = (
            "trend", "over time", "growth", "change", "evolution",
            "monthly", "quarterly", "yearly", "weekly trend",
            "increasing", "decreasing", "pattern",
        )
        if any(sig in text for sig in trend_signals):
            return INTENT_TREND

        # COMPARISON: compare two entities or metrics
        comparison_signals = (
            "compare", " vs ", "versus", "difference", "minus",
            "margin", "net ", "deduct", "subtract",
        )
        if any(sig in text for sig in comparison_signals):
            return INTENT_COMPARISON

        # RANKING: wants top/bottom/highest/lowest
        ranking_signals = (
            "highest", "lowest", "most", "least", "top ", "bottom",
            "biggest", "smallest", "best", "worst", "largest",
            "which .* has the", "which .* have the",
        )
        if any(re.search(sig, text) for sig in ranking_signals):
            return INTENT_RANKING

        # GROUPING: wants results broken down by category (check BEFORE count)
        grouping_signals = ("each", "per ", "by ", "group", "breakdown", "every", "across")
        if any(sig in text for sig in grouping_signals):
            return INTENT_GROUPING

        # COUNT: wants a count of records
        count_signals = ("how many", "count", "number of")
        if any(sig in text for sig in count_signals):
            return INTENT_COUNT

        # AGGREGATION: wants sum/avg/min/max
        agg_signals = ("total", "sum", "average", "avg", "minimum", "maximum", "min ", "max ")
        if any(sig in text for sig in agg_signals):
            return INTENT_AGGREGATION

        # FILTERING: wants to find/filter specific records
        filtering_signals = ("find ", "where ", "status ", "active", "inactive", "pending", "completed")
        if any(sig in text for sig in filtering_signals):
            return INTENT_FILTERING

        # ANALYSIS: wants analysis/insights
        analysis_signals = ("analysis", "analyze", "insight", "correlation", "distribute", "proportion")
        if any(sig in text for sig in analysis_signals):
            return INTENT_ANALYSIS

        # DETAIL: default — wants to see records
        return INTENT_DETAIL

    # ── Plan builders per intent ──────────────────────────────────────────

    @classmethod
    def _plan_count(cls, message: str, text: str, schema: DatabaseSchema,
                    mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a COUNT plan."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table to count.")

        filters: List[FilterSpec] = []
        status_cols = mapper.find_status_columns(table)
        if status_cols and "active" in text:
            filters.append(FilterSpec(table=table, column=status_cols[0], operator="=", value="Active"))
        if status_cols and "inactive" in text:
            filters.append(FilterSpec(table=table, column=status_cols[0], operator="=", value="Inactive"))

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_COUNT, tables=[table],
            select=[SelectExpr(expr_type="aggregate", table=table, column="*", operation="COUNT", alias="count")],
            filters=filters,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_aggregation(cls, message: str, text: str, schema: DatabaseSchema,
                          mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build an AGGREGATION plan (SUM, AVG, MIN, MAX)."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table contains the requested metric.")

        amount_cols = mapper.find_amount_columns(text, table)
        if not amount_cols:
            return cls.unsupported(f"No numeric metric column was found on table '{table}'.")

        column = amount_cols[0]
        operation = mapper.infer_metric_type(text)
        alias = f"{operation.lower()}_{column}"

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_AGGREGATION, tables=[table],
            select=[SelectExpr(expr_type="aggregate", table=table, column=column, operation=operation, alias=alias)],
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_ranking(cls, message: str, text: str, schema: DatabaseSchema,
                      mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a RANKING plan (highest/lowest/top/bottom)."""
        tables_matched = mapper.match_tables(text, limit=2)

        if len(tables_matched) >= 2:
            t1, t2 = tables_matched[0][0], tables_matched[1][0]
            t1_amounts = mapper.find_amount_columns(text, t1)
            t2_amounts = mapper.find_amount_columns(text, t2)
            if t1_amounts and not t2_amounts:
                measure_table, group_table = t1, t2
            elif t2_amounts and not t1_amounts:
                measure_table, group_table = t2, t1
            else:
                measure_table, group_table = t1, t2

            if measure_table in available and group_table in available:
                joins, join_error = cls._build_joins(schema, [measure_table, group_table])
                if join_error:
                    return cls.unsupported(join_error)

                name_cols = mapper.find_name_columns(group_table)
                name_col = name_cols[0] if name_cols else None
                if not name_col:
                    return cls.unsupported(f"Could not find a name column on '{group_table}'.")

                amount_cols = mapper.find_amount_columns(text, measure_table)
                count_indicators = ("employee", "customer", "order", "invoice", "project",
                                    "student", "patient", "shipment", "ticket")
                use_count = any(t in text for t in count_indicators) and not amount_cols

                if use_count:
                    operation, select_col, alias = "COUNT", "*", "count"
                else:
                    if not amount_cols:
                        return cls.unsupported(f"No numeric column found on '{measure_table}'.")
                    operation, select_col, alias = "SUM", amount_cols[0], f"total_{amount_cols[0]}"

                direction = "ASC" if "lowest" in text or "least" in text else "DESC"
                plan = QueryPlan(
                    tool="run_sql_plan", intent=INTENT_RANKING,
                    tables=[measure_table, group_table], joins=joins,
                    select=[
                        SelectExpr(expr_type="column", table=group_table, column=name_col, alias=name_col),
                        SelectExpr(expr_type="aggregate", table=measure_table, column=select_col, operation=operation, alias=alias),
                    ],
                    group_by=[f"{group_table}.{name_col}"],
                    order_by=[OrderBySpec(alias_or_column=alias, direction=direction)],
                )
                return cls._compat_fields(plan)

        elif len(tables_matched) == 1:
            table = tables_matched[0][0]
            if table in available:
                direction = "DESC" if "highest" in text or "most" in text or "top" in text else "ASC"
                name_cols = mapper.find_name_columns(table)
                amount_cols = mapper.find_amount_columns(text, table)
                if not amount_cols:
                    num_cols = [c for c in schema.find_numeric_columns(table) if not c.endswith("_id") and c != "id"]
                    amount_cols = num_cols[:1]

                if amount_cols:
                    select_exprs = [SelectExpr(expr_type="column", table=table, column=col, alias=col) for col in name_cols[:2]]
                    select_exprs.append(SelectExpr(expr_type="column", table=table, column=amount_cols[0], alias=amount_cols[0]))
                    plan = QueryPlan(
                        tool="run_sql_plan", intent=INTENT_RANKING, tables=[table],
                        select=select_exprs,
                        order_by=[OrderBySpec(alias_or_column=amount_cols[0], direction=direction)],
                        limit=100,
                    )
                    return cls._compat_fields(plan)

        return cls.unsupported("I could not determine the tables and columns for ranking.")

    @classmethod
    def _plan_grouping(cls, message: str, text: str, schema: DatabaseSchema,
                       mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a GROUPING plan (results grouped by category)."""
        pair = mapper.find_two_table_pair(text)
        if not pair:
            return cls.unsupported("I could not find two tables to group and aggregate.")

        measure_table, group_table = pair
        if measure_table not in available or group_table not in available:
            return cls.unsupported("The matched tables are not available.")

        joins, join_error = cls._build_joins(schema, [measure_table, group_table])
        if join_error:
            return cls.unsupported(join_error)

        name_cols = mapper.find_name_columns(group_table)
        name_col = name_cols[0] if name_cols else schema.safe_columns(group_table)[0]

        amount_cols = mapper.find_amount_columns(text, measure_table)
        metric = mapper.infer_metric_type(text)

        if metric != "COUNT" and amount_cols:
            operation = "SUM" if metric == "SUM" else metric
            alias = f"total_{amount_cols[0]}"
            select_col = amount_cols[0]
        else:
            operation = "COUNT"
            alias = "count"
            select_col = "*"

        order_dir = "DESC" if "highest" in text or "most" in text or "top" in text else "ASC"
        limit = 1 if "highest" in text or "most" in text or "which" in text or "top" in text else None

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_GROUPING,
            tables=[measure_table, group_table], joins=joins,
            select=[
                SelectExpr(expr_type="column", table=group_table, column=name_col, alias=name_col),
                SelectExpr(expr_type="aggregate", table=measure_table, column=select_col, operation=operation, alias=alias),
            ],
            group_by=[f"{group_table}.{name_col}"],
            order_by=[OrderBySpec(alias_or_column=alias, direction=order_dir)],
            limit=limit,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_filtering(cls, message: str, text: str, schema: DatabaseSchema,
                        mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a FILTERING plan (WHERE-based filtering)."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table to filter.")

        name_cols = mapper.find_name_columns(table)
        columns = schema.safe_columns(table)[:6]
        if name_cols and name_cols[0] not in columns:
            columns = [name_cols[0]] + columns

        filters: List[FilterSpec] = []

        # Detect status-based filters
        status_cols = mapper.find_status_columns(table)
        if status_cols:
            for keyword in ("active", "inactive", "pending", "completed", "cancelled", "delivered", "shipped"):
                if keyword in text:
                    filters.append(FilterSpec(
                        table=table, column=status_cols[0],
                        operator="=", value=keyword.capitalize(),
                    ))

        limit = 10
        match = re.search(r"\b(\d+)\b", text)
        if match:
            limit = min(int(match.group(1)), 50)

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_FILTERING, tables=[table],
            select=[SelectExpr(expr_type="column", table=table, column=col, alias=col) for col in columns],
            filters=filters, limit=limit,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_comparison(cls, message: str, text: str, schema: DatabaseSchema,
                         mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a COMPARISON plan (compare two metrics or entities)."""
        pair = mapper.find_two_table_pair(text)
        if pair is None:
            tables_matched = mapper.match_tables(text, limit=2)
            if len(tables_matched) >= 2:
                t1, t2 = tables_matched[0][0], tables_matched[1][0]
                if t1 in available and t2 in available:
                    pair = (t1, t2)

        if pair:
            t1, t2 = pair
            if t1 in available and t2 in available:
                rev_cols = mapper.find_amount_columns(text, t1)
                exp_cols = mapper.find_amount_columns(text, t2)
                if rev_cols and exp_cols:
                    plan = QueryPlan(
                        tool="run_sql_plan", intent=INTENT_COMPARISON,
                        tables=[t1, t2],
                        calculation={
                            "operation": "subtract",
                            "left": {"table": t1, "operation": "SUM", "column": rev_cols[0], "alias": f"total_{t1}"},
                            "right": {"table": t2, "operation": "SUM", "column": exp_cols[0], "alias": f"total_{t2}"},
                            "alias": f"{t1}_minus_{t2}",
                        },
                        select=[
                            SelectExpr(expr_type="calc", alias=f"total_{t1}"),
                            SelectExpr(expr_type="calc", alias=f"total_{t2}"),
                            SelectExpr(expr_type="calc", alias=f"{t1}_minus_{t2}"),
                        ],
                    )
                    return cls._compat_fields(plan)

        return cls.unsupported(
            "I could not determine two comparable metrics from the question."
        )

    @classmethod
    def _plan_percentage(cls, message: str, text: str, schema: DatabaseSchema,
                         mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a percentage plan."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table to use for the percentage calculation.")

        status_cols = mapper.find_status_columns(table)
        if not status_cols:
            return cls.unsupported(f"Table '{table}' has no status column for percentage calculations.")

        value = None
        for word in text.split():
            if word not in ("percentage", "percent", "of", "the", "is", "are", "what", "how"):
                value = word.capitalize()
                break
        if value is None:
            return cls.unsupported("Specify which status to use for the percentage (for example, active).")

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_AGGREGATION, tables=[table],
            select=[
                SelectExpr(
                    expr_type="aggregate", table=table, column="*", operation="PERCENT",
                    alias="percentage", filter_column=status_cols[0], filter_value=value,
                )
            ],
            table=table,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_trend(cls, message: str, text: str, schema: DatabaseSchema,
                    mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a TREND plan — group by time period."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table to analyze for trends.")

        # Find a date/time column
        date_col = cls._find_date_column(schema, table)
        if not date_col:
            return cls.unsupported(f"Table '{table}' has no date column to analyze trends over time.")

        amount_cols = mapper.find_amount_columns(text, table)
        if amount_cols:
            select_col = amount_cols[0]
            operation = "SUM"
            alias = f"total_{select_col}"
        else:
            select_col = "*"
            operation = "COUNT"
            alias = "count"

        # Determine the time bucket (monthly by default)
        time_bucket = f"DATE_TRUNC('month', {table}.{date_col})"

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_TREND, tables=[table],
            select=[
                SelectExpr(expr_type="column", table=table, column=date_col, alias="period"),
                SelectExpr(expr_type="aggregate", table=table, column=select_col, operation=operation, alias=alias),
            ],
            group_by=[f"{time_bucket} AS period"],
            order_by=[OrderBySpec(alias_or_column="period", direction="ASC")],
            limit=24,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_time_based(cls, message: str, text: str, schema: DatabaseSchema,
                         mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a TIME_BASED plan — filter by date range."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table to query.")

        date_col = cls._find_date_column(schema, table)
        if not date_col:
            return cls.unsupported(f"Table '{table}' has no date column for time-based filtering.")

        name_cols = mapper.find_name_columns(table)
        amount_cols = mapper.find_amount_columns(text, table)

        select_cols = [col for col in name_cols[:2]]
        if amount_cols:
            select_cols.append(amount_cols[0])
        if not select_cols:
            select_cols = schema.safe_columns(table)[:4]

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_TIME_BASED, tables=[table],
            select=[SelectExpr(expr_type="column", table=table, column=col, alias=col) for col in select_cols],
            limit=100,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_detail(cls, message: str, text: str, schema: DatabaseSchema,
                     mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build a DETAIL plan — find and list records."""
        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if table is None:
            return cls.unsupported(
                "I could not map that question to any table in the connected schema. "
                f"Available tables include: {', '.join(sorted(available))}."
            )

        name_cols = mapper.find_name_columns(table)
        name_col = name_cols[0] if name_cols else None
        columns = schema.safe_columns(table)[:6]

        if any(token in text for token in ("name", "called")) and name_col:
            columns = [name_col]
        elif name_col and name_col not in columns:
            columns = [name_col] + columns

        limit = 1 if any(token in text for token in ("name", "which", "who")) else 10
        match = re.search(r"\b(\d+)\b", text)
        if match:
            limit = min(int(match.group(1)), 50)

        filters: List[FilterSpec] = []
        status_cols = mapper.find_status_columns(table)
        if status_cols and "active" in text:
            filters.append(FilterSpec(table=table, column=status_cols[0], operator="=", value="Active"))

        plan = QueryPlan(
            tool="run_sql_plan", intent=INTENT_DETAIL, tables=[table],
            select=[SelectExpr(expr_type="column", table=table, column=col, alias=col) for col in columns],
            filters=filters, limit=limit,
        )
        return cls._compat_fields(plan)

    @classmethod
    def _plan_analysis(cls, message: str, text: str, schema: DatabaseSchema,
                       mapper: BusinessTermMapper, available: Set[str]) -> QueryPlan:
        """Build an ANALYSIS plan — aggregate and group for insights."""
        # Analysis often means grouped aggregation with counts
        pair = mapper.find_two_table_pair(text)
        if pair:
            return cls._plan_grouping(message, text, schema, mapper, available)

        tables_matched = mapper.match_tables(text, limit=1)
        table = tables_matched[0][0] if tables_matched else None
        if not table:
            return cls.unsupported("I could not determine which table to analyze.")

        # Find status columns for distribution analysis
        status_cols = mapper.find_status_columns(table)
        if status_cols:
            plan = QueryPlan(
                tool="run_sql_plan", intent=INTENT_ANALYSIS, tables=[table],
                select=[
                    SelectExpr(expr_type="column", table=table, column=status_cols[0], alias=status_cols[0]),
                    SelectExpr(expr_type="aggregate", table=table, column="*", operation="COUNT", alias="count"),
                ],
                group_by=[f"{table}.{status_cols[0]}"],
                order_by=[OrderBySpec(alias_or_column="count", direction="DESC")],
            )
            return cls._compat_fields(plan)

        # Fallback: count records
        return cls._plan_count(message, text, schema, mapper, available)

    # ── Helpers ───────────────────────────────────────────────────────────

    @classmethod
    def _find_date_column(cls, schema: DatabaseSchema, table: str) -> Optional[str]:
        """Find a date/timestamp column in a table."""
        date_keywords = ("date", "created", "updated", "timestamp", "time",
                         "day", "month", "year", "period", "deadline")
        for col in schema.columns_for(table):
            col_lower = col.lower()
            if any(kw in col_lower for kw in date_keywords):
                col_type = schema.get_column_type(table, col).lower()
                if any(dt in col_type for dt in ("date", "time", "timestamp")):
                    return col
        # Fallback: any column with date-like name
        for col in schema.columns_for(table):
            col_lower = col.lower()
            if any(kw in col_lower for kw in date_keywords):
                return col
        return None

    # ── Main entry point ──────────────────────────────────────────────────

    @classmethod
    def build_plan(
        cls,
        message: str,
        schema: DatabaseSchema,
        available_tables: Optional[Set[str]] = None,
    ) -> QueryPlan:
        """Build a query plan using schema-driven term matching.

        Flow:
            Question → Classify intent → Extract entities → Match tables →
            Match columns → Discover FK joins → Build structured plan → Validate
        """
        if not message or not str(message).strip():
            return cls.unsupported("The question was empty.")

        text = cls._normalize(message)
        if cls._is_illegal(text):
            return cls.unsupported("That request looks unsafe or asks for restricted information.")

        available = set(available_tables or schema.table_names())
        if not available:
            return cls.unsupported("No tables are available in the connected database.")

        mapper = BusinessTermMapper(schema)

        # ── Special cases that need specific handling ──

        # Percentage questions
        if "percent" in text or "percentage" in text:
            return cls._plan_percentage(message, text, schema, mapper, available)

        # ── Classify intent ──
        intent = cls._classify_intent(text)

        # Route to the appropriate plan builder
        builders = {
            INTENT_COUNT: cls._plan_count,
            INTENT_AGGREGATION: cls._plan_aggregation,
            INTENT_RANKING: cls._plan_ranking,
            INTENT_GROUPING: cls._plan_grouping,
            INTENT_FILTERING: cls._plan_filtering,
            INTENT_COMPARISON: cls._plan_comparison,
            INTENT_TREND: cls._plan_trend,
            INTENT_TIME_BASED: cls._plan_time_based,
            INTENT_DETAIL: cls._plan_detail,
            INTENT_ANALYSIS: cls._plan_analysis,
        }

        builder = builders.get(intent, cls._plan_detail)
        return builder(message, text, schema, mapper, available)
