"""Result Analysis Engine — computes statistical insights from query results.

Provides analysis capabilities WITHOUT fabricating causal explanations.
All outputs are strictly FACT-based: what the data shows.

Capabilities:
    - Difference between two values
    - Percentage difference
    - Growth rate (period-over-period)
    - Trend direction (increasing / decreasing / stable / mixed)
    - Highest, lowest, average, median
    - Comparison across groups
    - Distribution analysis
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AnalysisResult:
    """Structured output from a result analysis.

    All fields are factual observations — no causal claims.
    """
    # Core statistics
    count: int = 0
    total: Optional[float] = None
    average: Optional[float] = None
    median: Optional[float] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    std_dev: Optional[float] = None

    # Grouping
    min_entity: Optional[str] = None  # entity with the minimum value
    max_entity: Optional[str] = None  # entity with the maximum value

    # Comparisons
    difference: Optional[float] = None  # max - min
    pct_difference: Optional[float] = None  # (max - min) / min * 100

    # Trend
    trend_direction: Optional[str] = None  # "increasing" | "decreasing" | "stable" | "mixed"
    growth_rate: Optional[float] = None  # (last - first) / first * 100

    # For multi-row grouping
    groups: List[Dict[str, Any]] = field(default_factory=list)

    # The raw data that produced this analysis (for traceability)
    source_rows: int = 0


def _safe_float(value: Any) -> Optional[float]:
    """Convert a value to float safely."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_numeric_values(
    rows: List[Dict[str, Any]],
    value_key: Optional[str] = None,
) -> List[float]:
    """Extract numeric values from rows.

    If value_key is provided, extract only that column.
    Otherwise, extract the first numeric value from each row.
    """
    values: List[float] = []
    for row in rows:
        if value_key and value_key in row:
            v = _safe_float(row[value_key])
            if v is not None:
                values.append(v)
        else:
            for k, v in row.items():
                if k.endswith("_id") or k == "id":
                    continue
                fv = _safe_float(v)
                if fv is not None:
                    values.append(fv)
                    break
    return values


def _extract_name_value_pairs(
    rows: List[Dict[str, Any]],
    name_key: Optional[str] = None,
    value_key: Optional[str] = None,
) -> List[Tuple[str, float]]:
    """Extract (name, value) pairs from rows for grouped analysis."""
    pairs: List[Tuple[str, float]] = []
    for row in rows:
        # Determine name key
        nk = name_key
        if not nk:
            for k in row.keys():
                if "name" in k or k.endswith("_name"):
                    nk = k
                    break
            if not nk:
                nk = next((k for k in row.keys() if k != "id" and not k.endswith("_id")), None)

        # Determine value key
        vk = value_key
        if not vk:
            for k in row.keys():
                if k == nk or k.endswith("_id") or k == "id":
                    continue
                fv = _safe_float(row.get(k))
                if fv is not None:
                    vk = k
                    break

        if nk and vk:
            name = str(row.get(nk, "unknown"))
            val = _safe_float(row.get(vk))
            if val is not None:
                pairs.append((name, val))
    return pairs


# ─── Analysis Functions ────────────────────────────────────────────────────


def compute_basic_stats(rows: List[Dict[str, Any]], value_key: Optional[str] = None) -> AnalysisResult:
    """Compute basic statistics (count, avg, min, max, median, std dev)."""
    values = _extract_numeric_values(rows, value_key)
    result = AnalysisResult(source_rows=len(rows), count=len(values))

    if not values:
        return result

    result.total = sum(values)
    result.average = statistics.mean(values)
    result.median = statistics.median(values)
    result.minimum = min(values)
    result.maximum = max(values)

    if len(values) >= 2:
        result.std_dev = statistics.stdev(values)
        result.difference = result.maximum - result.minimum
        if result.minimum != 0:
            result.pct_difference = (result.difference / abs(result.minimum)) * 100

    return result


def compute_grouped_analysis(
    rows: List[Dict[str, Any]],
    name_key: Optional[str] = None,
    value_key: Optional[str] = None,
) -> AnalysisResult:
    """Compute grouped analysis — find min/max entities, distribution."""
    pairs = _extract_name_value_pairs(rows, name_key, value_key)
    result = AnalysisResult(source_rows=len(rows))

    if not pairs:
        return result

    values = [v for _, v in pairs]
    result.count = len(values)
    result.total = sum(values)
    result.average = statistics.mean(values)
    result.minimum = min(values)
    result.maximum = max(values)

    # Find entities
    for name, val in pairs:
        if val == result.minimum:
            result.min_entity = name
        if val == result.maximum:
            result.max_entity = name

    result.difference = result.maximum - result.minimum
    if result.minimum != 0:
        result.pct_difference = (result.difference / abs(result.minimum)) * 100

    # Store groups for display
    result.groups = [{"name": name, "value": val} for name, val in pairs]

    return result


def compute_trend(rows: List[Dict[str, Any]], value_key: Optional[str] = None) -> AnalysisResult:
    """Compute trend analysis from time-ordered rows.

    Assumes rows are ordered chronologically (oldest first).
    """
    values = _extract_numeric_values(rows, value_key)
    result = AnalysisResult(source_rows=len(rows), count=len(values))

    if len(values) < 2:
        if values:
            result.trend_direction = "single_point"
            result.average = values[0]
        return result

    result.average = statistics.mean(values)
    result.minimum = min(values)
    result.maximum = max(values)

    # Growth rate: (last - first) / |first| * 100
    first_val = values[0]
    last_val = values[-1]
    if first_val != 0:
        result.growth_rate = ((last_val - first_val) / abs(first_val)) * 100

    # Trend direction: check sign of consecutive differences
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    positive = sum(1 for d in diffs if d > 0)
    negative = sum(1 for d in diffs if d < 0)
    flat = sum(1 for d in diffs if d == 0)

    if positive > 0 and negative == 0:
        result.trend_direction = "increasing"
    elif negative > 0 and positive == 0:
        result.trend_direction = "decreasing"
    elif positive == 0 and negative == 0:
        result.trend_direction = "stable"
    else:
        # Mixed — more increasing than decreasing or vice versa
        if positive > negative:
            result.trend_direction = "mostly_increasing"
        elif negative > positive:
            result.trend_direction = "mostly_decreasing"
        else:
            result.trend_direction = "mixed"

    return result


def compute_comparison(
    rows: List[Dict[str, Any]],
    value_key: Optional[str] = None,
) -> AnalysisResult:
    """Compute comparison analysis between the top two values.

    Designed for ranking results where the top two rows represent
    the entities to compare.
    """
    pairs = _extract_name_value_pairs(rows, value_key=value_key)
    result = AnalysisResult(source_rows=len(rows))

    if len(pairs) < 2:
        if len(pairs) == 1:
            result.max_entity = pairs[0][0]
            result.maximum = pairs[0][1]
        return result

    # Sort by value descending
    pairs.sort(key=lambda x: x[1], reverse=True)

    result.max_entity = pairs[0][0]
    result.maximum = pairs[0][1]
    result.min_entity = pairs[1][0]
    result.minimum = pairs[1][1]
    result.count = len(pairs)

    result.difference = result.maximum - result.minimum
    if result.minimum != 0:
        result.pct_difference = (result.difference / abs(result.minimum)) * 100

    result.groups = [{"name": name, "value": val} for name, val in pairs]

    return result


def compute_distribution(rows: List[Dict[str, Any]], value_key: Optional[str] = None) -> AnalysisResult:
    """Compute distribution analysis — how values are spread across groups."""
    pairs = _extract_name_value_pairs(rows, value_key)
    result = AnalysisResult(source_rows=len(rows))

    if not pairs:
        return result

    values = [v for _, v in pairs]
    result.count = len(values)
    result.total = sum(values)
    result.average = statistics.mean(values)

    if len(values) >= 2:
        result.std_dev = statistics.stdev(values)
        result.minimum = min(values)
        result.maximum = max(values)

    # Sort groups by value descending
    pairs.sort(key=lambda x: x[1], reverse=True)
    for name, val in pairs:
        pct_of_total = (val / result.total * 100) if result.total else 0
        result.groups.append({
            "name": name,
            "value": val,
            "pct_of_total": round(pct_of_total, 1),
        })

    return result


def analyze_result(
    rows: List[Dict[str, Any]],
    intent: str,
    question: str = "",
    value_key: Optional[str] = None,
    name_key: Optional[str] = None,
) -> AnalysisResult:
    """Main entry point — route to the appropriate analysis function.

    Args:
        rows: Result rows from the database query.
        intent: The intent type from the query plan.
        question: The original user question (for context).
        value_key: Column name containing numeric values (auto-detected if None).
        name_key: Column name containing entity names (auto-detected if None).

    Returns:
        AnalysisResult with computed statistics.
    """
    if not rows:
        return AnalysisResult()

    q = question.lower()

    # Route based on intent
    if intent in ("trend", "time_based"):
        return compute_trend(rows, value_key)

    if intent in ("ranking", "grouping", "analysis"):
        # Check if this is a comparison between specific entities
        if intent == "ranking" and len(rows) >= 2:
            return compute_comparison(rows, value_key)
        return compute_grouped_analysis(rows, name_key, value_key)

    if intent == "comparison":
        return compute_comparison(rows, value_key)

    if intent == "analysis":
        return compute_distribution(rows, value_key)

    # Default: basic stats
    return compute_basic_stats(rows, value_key)
