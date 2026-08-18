from __future__ import annotations

from typing import Any, Dict, List, Optional

from .query_planner import QueryPlan


def _fmt_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}"
    return f"{number:,.2f}"


def format_answer(question: str, plan: QueryPlan, result: Dict[str, Any]) -> str:
    if plan.tool == "unsupported" or plan.reason:
        return plan.reason or "I could not answer that question using the available database data."

    error = result.get("error")
    if error:
        return f"I could not answer that question because {error}"

    rows: List[Dict[str, Any]] = result.get("rows") or []
    if not rows:
        return "The query ran successfully, but no matching rows were found in the database."

    intent = plan.intent
    first = rows[0]

    if intent == "calculation" or plan.calculation:
        alias = (plan.calculation or {}).get("alias", "revenue_minus_expenses")
        left_alias = (plan.calculation or {}).get("left", {}).get("alias", "total_revenue")
        right_alias = (plan.calculation or {}).get("right", {}).get("alias", "total_expenses")
        return (
            f"Total revenue is {_fmt_number(first.get(left_alias))}, "
            f"total expenses are {_fmt_number(first.get(right_alias))}, "
            f"and revenue minus expenses is {_fmt_number(first.get(alias))}."
        )

    if intent == "percentage":
        key = next(iter(first.keys()))
        return f"The calculated percentage is {_fmt_number(first.get(key))}%."

    if intent in {"aggregate", "count"}:
        key = next(iter(first.keys()))
        value = first.get(key)
        if intent == "count" or str(key).lower() == "count":
            table = plan.tables[0] if plan.tables else "records"
            return f"There are {_fmt_number(value)} {table}."
        if "avg" in str(key).lower() or "average" in question.lower():
            return f"The average is {_fmt_number(value)}."
        if "sum" in str(key).lower() or "total" in question.lower():
            return f"The total is {_fmt_number(value)}."
        return f"The result is {_fmt_number(value)}."

    if intent in {"group_aggregate", "top_group"}:
        if intent == "top_group":
            q_lower = question.lower()
            name_keys = [k for k in first.keys() if "name" in k or k.endswith("_name")]
            if "first_name" in first and "last_name" in first:
                display_name = f"{first['first_name']} {first['last_name']}"
            elif name_keys:
                display_name = first[name_keys[0]]
            else:
                display_name = None

            metric_candidates = [k for k in first.keys() if k not in tuple(name_keys) and k not in ("first_name", "last_name")]
            metric_key = metric_candidates[-1] if metric_candidates else None
            if metric_key:
                if "employee" in q_lower or "employees" in q_lower:
                    metric_label = "employees" if str(metric_key).lower() == "count" else str(metric_key)
                elif "order" in q_lower or "orders" in q_lower:
                    metric_label = "orders"
                elif "customer" in q_lower or "customers" in q_lower:
                    metric_label = "customers"
                elif "expense" in q_lower:
                    metric_label = "expenses"
                elif "revenue" in q_lower:
                    metric_label = "revenue"
                elif "budget" in q_lower:
                    metric_label = "budget"
                elif "salary" in q_lower:
                    metric_label = "salary"
                else:
                    metric_label = str(metric_key)
                direction_label = "lowest" if any(token in q_lower for token in ("lowest", "least", "smallest")) else "highest"
                top_value = first[metric_key]
                tied = [row for row in rows if row.get(metric_key) == top_value]
                if len(tied) > 1:
                    if "first_name" in first and "last_name" in first:
                        names = ", ".join(f"{row['first_name']} {row['last_name']}" for row in tied)
                    elif name_keys:
                        names = ", ".join(str(row.get(name_keys[0])) for row in tied)
                    else:
                        names = str(len(tied))
                    return f"{names} have the {direction_label} {metric_label} ({_fmt_number(top_value)})."
                if display_name:
                    return (
                        f"{display_name} has the {direction_label} {metric_label} "
                        f"({_fmt_number(first[metric_key])})."
                    )
        lines = []
        for row in rows:
            name_key = next((k for k in row.keys() if "name" in k), None)
            metric_key = next((k for k in row.keys() if k != name_key), None)
            if name_key and metric_key is not None:
                lines.append(f"- {row[name_key]}: {_fmt_number(row[metric_key])}")
            else:
                parts = [
                    f"{key}={_fmt_number(value) if isinstance(value, (int, float)) else value}"
                    for key, value in row.items()
                ]
                lines.append("- " + ", ".join(parts))
        return "Here are the grouped results:\n" + "\n".join(lines)

    if len(rows) == 1:
        if len(first) == 1:
            key, value = next(iter(first.items()))
            if "name" in key:
                return f"The name is {value}."
            return f"Here is what I found: {key}={value}."
        summary = ", ".join(f"{key}={value}" for key, value in first.items() if value is not None)
        return f"Here is what I found: {summary}."

    return f"I found {len(rows)} matching records in the database."


def _extract_generated_suffix(prompt: str, generated: str) -> str:
    text = (generated or "").strip()
    if text.startswith(prompt):
        return text[len(prompt):].strip()
    # Some generators echo part of the prompt; keep the last non-empty line.
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
    # Keep polish only when it preserves at least one numeric fact from the draft.
    import re

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
    except Exception as exc:  # pragma: no cover
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
    except Exception as exc:  # pragma: no cover
        meta["llm_error"] = str(exc)
    return {"answer": deterministic_answer, **meta}
