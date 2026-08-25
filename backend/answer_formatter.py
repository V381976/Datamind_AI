"""Answer Formatter — generates human-readable answers from query results.

Handles all 10 intent types with:
    - Statistical analysis (via result_analyzer)
    - Tie handling (e.g., "Engineering and Sales both have the highest count at 4")
    - Table/list display for multi-row results
    - FACT vs INFERENCE separation
    - Detailed explanations alongside raw data
    - All labels derived dynamically from schema — no hardcoded names
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .query_planner import (
    INTENT_AGGREGATION, INTENT_ANALYSIS, INTENT_COMPARISON, INTENT_COUNT,
    INTENT_DETAIL, INTENT_FILTERING, INTENT_GROUPING, INTENT_RANKING,
    INTENT_TIME_BASED, INTENT_TREND, QueryPlan,
)
from .result_analyzer import (
    AnalysisResult,
    analyze_result,
    compute_basic_stats,
    compute_grouped_analysis,
    compute_trend,
    compute_comparison,
)


# ─── Utility Functions ─────────────────────────────────────────────────────


def _fmt_number(value: Any) -> str:
    """Format a number with commas and appropriate precision."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}"
    return f"{number:,.2f}"


def _fmt_pct(value: Any) -> str:
    """Format a percentage value."""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _humanize_column(col: str) -> str:
    """Convert a column name to a human-readable label."""
    return col.replace("_", " ").strip() if col else col


def _derive_metric_label(plan: QueryPlan, question: str) -> str:
    """Derive a human-readable metric label from the plan."""
    q = question.lower()

    if plan.select:
        first = plan.select[0]
        if first.expr_type == "aggregate":
            if first.operation in ("COUNT",):
                return "records"
            if first.column and first.column != "*":
                return _humanize_column(first.column)

    if plan.order_by:
        return _humanize_column(plan.order_by[0].alias_or_column)

    if plan.calculation:
        return _humanize_column(plan.calculation.get("alias", "result"))

    if "count" in q or "how many" in q:
        return "records"
    if "total" in q or "sum" in q:
        return "total"
    if "average" in q or "avg" in q:
        return "average"
    return "value"


def _get_display_name(row: Dict[str, Any], plan: QueryPlan) -> Optional[str]:
    """Extract a display name from a result row."""
    name_keys = [k for k in row.keys() if "name" in k or k.endswith("_name")]
    if "first_name" in row and "last_name" in row:
        return f"{row['first_name']} {row['last_name']}"
    if name_keys:
        return str(row[name_keys[0]])
    for k, v in row.items():
        if v is not None and k != "id" and not k.endswith("_id") and not k.startswith("count_"):
            return str(v)
    return None


def _get_metric_key(row: Dict[str, Any], exclude_name: bool = True) -> Optional[str]:
    """Find the metric (numeric) column in a result row."""
    name_keys = {k for k in row.keys() if "name" in k or k.endswith("_name")}
    skip_keys = name_keys | {"id"} | {k for k in row.keys() if k.endswith("_id")}
    if exclude_name:
        skip_keys |= {"first_name", "last_name"}

    candidates = []
    for k in row.keys():
        if k in skip_keys:
            continue
        v = row[k]
        if isinstance(v, (int, float)):
            candidates.append(k)
        elif v is not None:
            candidates.append(k)

    return candidates[-1] if candidates else None


def _render_table(rows: List[Dict[str, Any]], max_rows: int = 20) -> str:
    """Render rows as a formatted text table.

    | Name              | Count |
    |-------------------|-------|
    | Engineering       |    45 |
    | Sales             |    38 |
    """
    if not rows:
        return ""

    # Determine columns
    all_keys = list(rows[0].keys())
    # Put name-like columns first
    name_cols = [k for k in all_keys if "name" in k or k.endswith("_name")]
    other_cols = [k for k in all_keys if k not in name_cols]
    display_cols = name_cols + other_cols

    # Calculate column widths
    widths: Dict[str, int] = {}
    for col in display_cols:
        header_len = len(col)
        max_val_len = max(
            (len(str(row.get(col, ""))) for row in rows[:max_rows]),
            default=0,
        )
        widths[col] = max(header_len, max_val_len, 4) + 2

    # Header
    header = "| " + " | ".join(col.center(widths[col]) for col in display_cols) + " |"
    separator = "|" + "|".join("-" * (widths[col] + 2) for col in display_cols) + "|"

    # Rows
    lines = [header, separator]
    for row in rows[:max_rows]:
        cells = []
        for col in display_cols:
            val = row.get(col, "")
            if isinstance(val, (int, float)):
                cells.append(_fmt_number(val).rjust(widths[col]))
            else:
                cells.append(str(val)[:widths[col]].ljust(widths[col]))
        lines.append("| " + " | ".join(cells) + " |")

    if len(rows) > max_rows:
        lines.append(f"| ... and {len(rows) - max_rows} more rows |")

    return "\n".join(lines)


def _render_list(rows: List[Dict[str, Any]], max_items: int = 15) -> str:
    """Render rows as a bulleted list."""
    if not rows:
        return ""

    lines = []
    for i, row in enumerate(rows[:max_items]):
        name = None
        value = None
        for k, v in row.items():
            if "name" in k or k.endswith("_name"):
                name = v
            elif k != "id" and not k.endswith("_id") and isinstance(v, (int, float)):
                value = v
            elif k != "id" and not k.endswith("_id") and v is not None and value is None:
                value = v

        if name and value is not None:
            lines.append(f"{i+1}. {name}: {_fmt_number(value)}")
        elif name:
            lines.append(f"{i+1}. {name}")
        else:
            parts = [f"{k}={v}" for k, v in row.items() if v is not None]
            lines.append(f"{i+1}. {', '.join(parts)}")

    if len(rows) > max_items:
        lines.append(f"... and {len(rows) - max_items} more items")

    return "\n".join(lines)


def _find_ties(rows: List[Dict[str, Any]], metric_key: str) -> Dict[float, List[str]]:
    """Find tied values in the results.

    Returns a dict mapping value -> list of entity names with that value.
    """
    ties: Dict[float, List[str]] = {}
    for row in rows:
        val = row.get(metric_key)
        if val is None:
            continue
        fv = float(val) if not isinstance(val, float) else val
        name = None
        for k, v in row.items():
            if "name" in k or k.endswith("_name"):
                name = str(v)
                break
        if not name:
            name = str(row)
        ties.setdefault(fv, []).append(name)
    return ties


# ─── Intent-Specific Formatters ────────────────────────────────────────────


def _format_count(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a COUNT result with analysis."""
    if not rows:
        return "No records found."

    first = rows[0]
    key = next(iter(first.keys()))
    value = first.get(key)
    table = plan.tables[0] if plan.tables else "records"
    label = _humanize_column(table)

    fact = f"There {_fmt_number(value)} {label} in the database."

    # Add analysis for single-count if we also have filter info
    if plan.filters:
        filter_desc = " with " + " and ".join(
            f"{f.column} = {f.value}" for f in plan.filters
        )
        fact = f"There {_fmt_number(value)} {label}{filter_desc}."

    return fact


def _format_aggregation(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format an AGGREGATION result with statistical context."""
    if not rows:
        return "No data found for the aggregation."

    first = rows[0]
    key = next(iter(first.keys()))
    value = first.get(key)
    metric_label = _derive_metric_label(plan, question)
    q = question.lower()

    # Determine operation type
    if "avg" in str(key).lower() or "average" in q or "avg" in q:
        op_label = "average"
    elif "sum" in str(key).lower() or "total" in q:
        op_label = "total"
    elif "min" in str(key).lower() or "minimum" in q:
        op_label = "minimum"
    elif "max" in str(key).lower() or "maximum" in q:
        op_label = "maximum"
    else:
        op_label = "value"

    fact = f"The {op_label} {metric_label} is {_fmt_number(value)}."

    return fact


def _format_ranking(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a RANKING result with tie detection and analysis."""
    if not rows:
        return "No ranking data found."

    first = rows[0]
    display_name = _get_display_name(first, plan)
    metric_key = _get_metric_key(first)
    metric_label = _derive_metric_label(plan, question)

    q = question.lower()
    direction_label = "lowest" if any(t in q for t in ("lowest", "least", "smallest")) else "highest"

    if not metric_key:
        # Fallback: list all rows
        return "Here are the ranked results:\n" + _render_list(rows)

    top_value = first.get(metric_key)

    # Check for ties
    ties = _find_ties(rows, metric_key)
    tied_names = ties.get(float(top_value) if top_value is not None else 0, [])

    # FACT section
    facts: List[str] = []

    if len(tied_names) > 1:
        names_str = ", ".join(tied_names[:-1]) + " and " + tied_names[-1]
        facts.append(f"{names_str} have the {direction_label} {metric_label} at {_fmt_number(top_value)}.")
    elif display_name:
        facts.append(f"{display_name} has the {direction_label} {metric_label} at {_fmt_number(top_value)}.")

    # Add comparison if there are multiple rows
    if len(rows) >= 2:
        second_row = rows[1]
        second_val = second_row.get(metric_key)
        second_name = _get_display_name(second_row, plan)
        if second_val is not None and top_value is not None:
            diff = float(top_value) - float(second_val)
            if diff != 0 and second_val != 0:
                pct = (diff / abs(float(second_val))) * 100
                facts.append(
                    f"This is {_fmt_number(diff)} ({_fmt_pct(pct)}) "
                    f"{'higher' if diff > 0 else 'lower'} than {second_name or 'the next entry'}."
                )

    # Add table for context (show top 10)
    if len(rows) > 1:
        table = _render_table(rows[:10])
        if table:
            facts.append(f"\nTop results:\n{table}")

    return "\n\n".join(facts)


def _format_grouping(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a GROUPING result with tie detection and distribution analysis."""
    if not rows:
        return "No grouped data found."

    first = rows[0]
    metric_key = _get_metric_key(first)
    metric_label = _derive_metric_label(plan, question)

    q = question.lower()

    # Top-1 ranking within groups
    if plan.limit == 1 or len(rows) == 1:
        display_name = _get_display_name(first, plan)
        direction = "lowest" if any(t in q for t in ("lowest", "least")) else "highest"
        if display_name and metric_key:
            return f"{display_name} has the {direction} {metric_label} at {_fmt_number(first[metric_key])}."

    # Multi-group: show table + analysis
    facts: List[str] = []

    # Compute stats
    analysis = compute_grouped_analysis(rows)
    facts.append(f"Across {analysis.count} groups:")

    if analysis.min_entity and analysis.max_entity:
        if analysis.min_entity == analysis.max_entity:
            facts.append(
                f"**{analysis.max_entity}** has the highest {metric_label} "
                f"at {_fmt_number(analysis.maximum)}."
            )
        else:
            facts.append(
                f"**{analysis.max_entity}** has the highest {metric_label} "
                f"at {_fmt_number(analysis.maximum)}."
            )
            facts.append(
                f"**{analysis.min_entity}** has the lowest {metric_label} "
                f"at {_fmt_number(analysis.minimum)}."
            )
            if analysis.minimum != 0:
                pct = analysis.pct_difference or 0
                facts.append(
                    f"The range is {_fmt_number(analysis.difference)} "
                    f"({_fmt_pct(pct)} spread from lowest to highest)."
                )

    if analysis.average is not None:
        facts.append(f"Average across groups: {_fmt_number(analysis.average)}.")

    # Table
    table = _render_table(rows[:20])
    if table:
        facts.append(f"\nGroup breakdown:\n{table}")

    return "\n\n".join(facts)


def _format_filtering(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a FILTERING result with count and preview."""
    if not rows:
        return "No matching records found with the specified filters."

    facts: List[str] = []
    facts.append(f"Found {len(rows)} matching record{'s' if len(rows) != 1 else ''}.")

    if len(rows) <= 10:
        table = _render_table(rows)
        if table:
            facts.append(table)
    else:
        # Show first 5 and summary
        table = _render_table(rows[:5])
        if table:
            facts.append(f"First 5 results:\n{table}")
        facts.append(f"... and {len(rows) - 5} more records.")

    return "\n\n".join(facts)


def _format_comparison(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a COMPARISON result with analysis."""
    if not rows:
        return "I could not compute the comparison."

    # Calculation-based comparison (e.g., revenue - expenses)
    if plan.calculation:
        alias = plan.calculation.get("alias", "result")
        left_alias = plan.calculation.get("left", {}).get("alias", "left_value")
        right_alias = plan.calculation.get("right", {}).get("alias", "right_value")
        left_label = _humanize_column(left_alias.replace("total_", ""))
        right_label = _humanize_column(right_alias.replace("total_", ""))
        first = rows[0]

        left_val = first.get(left_alias)
        right_val = first.get(right_alias)
        diff_val = first.get(alias)

        facts: List[str] = []

        # FACT
        facts.append(
            f"**{left_label.title()}**: {_fmt_number(left_val)}\n"
            f"**{right_label.title()}**: {_fmt_number(right_val)}\n"
            f"**Difference**: {_fmt_number(diff_val)}"
        )

        # INFERENCE (only if data supports it)
        if left_val and right_val and float(right_val) != 0:
            pct = (float(diff_val) / abs(float(right_val))) * 100
            direction = "more" if float(diff_val) > 0 else "less"
            facts.append(
                f"{left_label.title()} is {_fmt_pct(abs(pct))} {direction} "
                f"than {right_label}."
            )

        return "\n\n".join(facts)

    # Entity-based comparison (ranking top 2)
    if len(rows) >= 2:
        analysis = compute_comparison(rows)
        facts: List[str] = []

        if analysis.max_entity and analysis.min_entity:
            facts.append(
                f"**{analysis.max_entity}**: {_fmt_number(analysis.maximum)}\n"
                f"**{analysis.min_entity}**: {_fmt_number(analysis.minimum)}"
            )
            if analysis.minimum != 0 and analysis.pct_difference is not None:
                facts.append(
                    f"{analysis.max_entity} is {_fmt_pct(analysis.pct_difference)} "
                    f"higher than {analysis.min_entity}."
                )

        return "\n\n".join(facts)

    # Single row
    first = rows[0]
    parts = [f"{k}={_fmt_number(v) if isinstance(v, (int, float)) else v}" for k, v in first.items()]
    return "Here is the comparison: " + ", ".join(parts) + "."


def _format_trend(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a TREND result with growth rate and direction analysis."""
    if not rows:
        return "No trend data found for the specified time period."

    metric_key = _get_metric_key(rows[0])
    if not metric_key:
        return f"I found {len(rows)} data points for the trend."

    # Compute trend analysis
    analysis = compute_trend(rows, metric_key)
    metric_label = _humanize_column(metric_key)

    facts: List[str] = []

    # Trend direction (FACT)
    if analysis.trend_direction:
        facts.append(f"The {metric_label} trend is **{analysis.trend_direction}**.")

    # Growth rate (FACT)
    if analysis.growth_rate is not None:
        direction = "increase" if analysis.growth_rate > 0 else "decrease"
        facts.append(
            f"Overall {direction} of {_fmt_pct(abs(analysis.growth_rate))} "
            f"from the earliest to the latest period."
        )

    # Range (FACT)
    if analysis.minimum is not None and analysis.maximum is not None:
        facts.append(
            f"Range: {_fmt_number(analysis.minimum)} to {_fmt_number(analysis.maximum)}."
        )

    if analysis.average is not None:
        facts.append(f"Average: {_fmt_number(analysis.average)}.")

    # Table
    table = _render_table(rows[:12])
    if table:
        facts.append(f"\nPeriod breakdown:\n{table}")

    return "\n\n".join(facts)


def _format_time_based(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a TIME_BASED result with count and preview."""
    if not rows:
        return "No records found for the specified time period."

    facts: List[str] = []
    facts.append(f"Found {len(rows)} records for the specified time period.")

    # Try to compute stats on any numeric columns
    metric_key = _get_metric_key(rows[0]) if rows else None
    if metric_key:
        values = [r.get(metric_key) for r in rows if r.get(metric_key) is not None]
        numeric_vals = []
        for v in values:
            try:
                numeric_vals.append(float(v))
            except (TypeError, ValueError):
                pass
        if numeric_vals:
            total = sum(numeric_vals)
            avg = total / len(numeric_vals)
            facts.append(f"Total: {_fmt_number(total)}, Average: {_fmt_number(avg)}.")

    if len(rows) <= 10:
        table = _render_table(rows)
        if table:
            facts.append(table)

    return "\n\n".join(facts)


def _format_analysis(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format an ANALYSIS result with full statistical breakdown."""
    if not rows:
        return "No data available for analysis."

    # Compute distribution analysis
    analysis = compute_grouped_analysis(rows)

    facts: List[str] = []
    facts.append(f"**Analysis of {len(rows)} records:**")

    if analysis.average is not None:
        facts.append(f"- Average: {_fmt_number(analysis.average)}")
    if analysis.median is not None:
        facts.append(f"- Median: {_fmt_number(analysis.median)}")
    if analysis.minimum is not None:
        facts.append(f"- Minimum: {_fmt_number(analysis.minimum)}")
    if analysis.maximum is not None:
        facts.append(f"- Maximum: {_fmt_number(analysis.maximum)}")
    if analysis.std_dev is not None:
        facts.append(f"- Standard deviation: {_fmt_number(analysis.std_dev)}")

    if analysis.min_entity and analysis.max_entity:
        facts.append(f"- Lowest: **{analysis.min_entity}** ({_fmt_number(analysis.minimum)})")
        facts.append(f"- Highest: **{analysis.max_entity}** ({_fmt_number(analysis.maximum)})")

    # Table
    table = _render_table(rows[:20])
    if table:
        facts.append(f"\nDetailed breakdown:\n{table}")

    return "\n".join(facts)


def _format_detail(plan: QueryPlan, rows: List[Dict[str, Any]], question: str) -> str:
    """Format a DETAIL (lookup/find) result."""
    if not rows:
        return "No matching records found in the database."

    if len(rows) == 1:
        first = rows[0]
        if len(first) == 1:
            key, value = next(iter(first.items()))
            if "name" in key:
                return f"The name is {value}."
            return f"Here is what I found: {key}={value}."

        # Single row with multiple columns
        parts = []
        for k, v in first.items():
            if v is not None:
                label = _humanize_column(k)
                if isinstance(v, (int, float)):
                    parts.append(f"**{label}**: {_fmt_number(v)}")
                else:
                    parts.append(f"**{label}**: {v}")
        return "Here is what I found:\n" + "\n".join(parts)

    # Multiple rows
    facts: List[str] = [f"Found {len(rows)} matching records:"]
    table = _render_table(rows[:10])
    if table:
        facts.append(table)
    if len(rows) > 10:
        facts.append(f"... and {len(rows) - 10} more records.")

    return "\n\n".join(facts)


# ─── Main Format Function ──────────────────────────────────────────────────

_FORMATTERS = {
    INTENT_COUNT: _format_count,
    INTENT_AGGREGATION: _format_aggregation,
    INTENT_RANKING: _format_ranking,
    INTENT_GROUPING: _format_grouping,
    INTENT_FILTERING: _format_filtering,
    INTENT_COMPARISON: _format_comparison,
    INTENT_TREND: _format_trend,
    INTENT_TIME_BASED: _format_time_based,
    INTENT_ANALYSIS: _format_analysis,
    INTENT_DETAIL: _format_detail,
}


def format_answer(
    question: str,
    plan: QueryPlan,
    result: Dict[str, Any],
    prior_context: Optional[str] = None,
) -> str:
    """Format a query plan + execution result into a human-readable answer.

    Features:
        - All 10 intent types supported
        - Statistical analysis integrated
        - Tie detection for rankings
        - Table/list rendering for multi-row results
        - Labels derived dynamically from schema
        - Prior context integration for follow-ups

    Args:
        question: The user's question.
        plan: The structured query plan.
        result: Execution result with rows and SQL.
        prior_context: Optional context from previous answer for follow-ups.
    """
    if plan.tool == "unsupported" or plan.reason:
        return plan.reason or "I could not answer that question using the available database data."

    error = result.get("error")
    if error:
        return f"I could not answer that question because {error}"

    rows: List[Dict[str, Any]] = result.get("rows") or []
    intent = plan.intent

    # Check for calculation intent (special handling)
    if intent == "comparison" and plan.calculation:
        return _format_comparison(plan, rows, question)

    # Get the formatter for this intent
    formatter = _FORMATTERS.get(intent, _format_detail)
    answer = formatter(plan, rows, question)

    # Prepend prior context if this is a follow-up
    if prior_context and answer:
        answer = f"Based on the previous result: {prior_context}\n\n{answer}"

    return answer


# ─── LLM Polish (safe) ────────────────────────────────────────────────────


def _extract_generated_suffix(prompt: str, generated: str) -> str:
    text = (generated or "").strip()
    if text.startswith(prompt):
        return text[len(prompt):].strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else text


def _is_safe_polish(deterministic_answer: str, polished: str) -> bool:
    text = (polished or "").strip()
    if len(text) < 3 or len(text) > 400:
        return False
    banned = ("question:", "facts:", "draft:", "rewrite the draft")
    lowered = text.lower()
    if any(token in lowered for token in banned):
        return False
    draft_numbers = set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", deterministic_answer))
    if not draft_numbers:
        return text.lower()[:40] in deterministic_answer.lower() or deterministic_answer.lower()[:40] in text.lower()
    polished_numbers = set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text))
    return bool(draft_numbers & polished_numbers)


def maybe_polish_with_custom_llm(question: str, deterministic_answer: str, result: Any) -> Dict[str, Any]:
    """Try the local custom GPT, but never replace accurate DB answers with unsafe text."""
    meta = {"llm_used": False, "llm_error": None, "llm": "custom-gpt"}
    try:
        import torch
        from inference.generate import generate_text
        from model.config import GPTConfig
        from model.gpt import GPTModel
        from tokenizer.tokenizer import CharTokenizer
    except Exception as exc:
        meta["llm_error"] = str(exc)
        return {"answer": deterministic_answer, **meta}

    try:
        from pathlib import Path

        checkpoint_path = Path("checkpoints/checkpoint_latest.pt")
        if not checkpoint_path.exists():
            meta["llm_error"] = "checkpoint_missing"
            return {"answer": deterministic_answer, **meta}

        tokenizer = CharTokenizer()
        model = GPTModel(
            GPTConfig(
                vocab_size=tokenizer.vocab_size,
                block_size=128,
                embedding_dim=256,
                n_heads=4,
                n_layers=4,
                dropout=0.1,
            )
        )
        checkpoint = torch.load(str(checkpoint_path), map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["model_state"])
        model.eval()
        prompt = f"Answer: {deterministic_answer}\n"
        generated = generate_text(model, tokenizer, prompt, max_new_tokens=20, temperature=0.1, top_k=10)
        polished = _extract_generated_suffix(prompt, generated or "")
        meta["llm_used"] = True
        if _is_safe_polish(deterministic_answer, polished):
            return {"answer": polished, **meta}
        meta["llm_error"] = "polish_rejected_kept_deterministic"
    except Exception as exc:
        meta["llm_error"] = str(exc)
    return {"answer": deterministic_answer, **meta}
