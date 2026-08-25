from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .schema_catalog import DatabaseSchema


# Common English pluralization / singularization rules
_PLURAL_SUFFIXES = [
    ("ies", "y"),
    ("ves", "f"),
    ("ves", "fe"),
    ("ses", "s"),
    ("xes", "x"),
    ("zes", "z"),
    ("ches", "ch"),
    ("shes", "sh"),
    ("es", ""),
    ("s", ""),
]

_ABBREVIATIONS: Dict[str, str] = {
    "qty": "quantity",
    "qtys": "quantity",
    "amt": "amount",
    "amt": "amount",
    "desc": "description",
    "info": "information",
    "addr": "address",
    "no": "number",
    "num": "number",
    "id": "identifier",
    "ts": "timestamp",
    "dt": "date",
    "fn": "first_name",
    "ln": "last_name",
    "ph": "phone",
    "addr": "address",
    "dob": "date_of_birth",
    "emp": "employee",
    "dept": "department",
    "cust": "customer",
    "prod": "product",
    "qty": "quantity",
    "pmt": "payment",
    "inv": "invoice",
    "txn": "transaction",
    "cat": "category",
    "mfg": "manufacturing",
    "mgr": "manager",
    "yr": "year",
    "mo": "month",
    "hr": "hour",
    "min": "minimum",
    "max": "maximum",
    "avg": "average",
    "cnt": "count",
    "pk": "primary_key",
    "fk": "foreign_key",
    "ref": "reference",
    "rec": "record",
    "mgr": "manager",
    "emp": "employee",
    "cust": "customer",
    "prod": "product",
    "dept": "department",
    "inv": "inventory",
    "qty": "quantity",
}


def _singularize(word: str) -> str:
    """Convert a plural word to its singular form."""
    word = word.lower().strip()
    if len(word) <= 3:
        return word
    for suffix, replacement in _PLURAL_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            candidate = word[: -len(suffix)] + replacement
            if len(candidate) >= 2:
                return candidate
    return word


def _tokenize(text: str) -> List[str]:
    """Extract meaningful lowercase tokens from text, splitting on non-alphanumeric."""
    text = text.lower()
    # Split camelCase
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Split on non-alphanumeric
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


def _expand_abbreviation(token: str) -> str:
    """Expand common abbreviations."""
    return _ABBREVIATIONS.get(token, token)


class BusinessTermMapper:
    """Maps business vocabulary in user questions to actual schema elements.

    Uses token overlap, singularization, abbreviation expansion, and
    substring matching — no external LLM or embedding model needed.
    """

    def __init__(self, catalog: DatabaseSchema) -> None:
        self.catalog = catalog  # Accepts DatabaseSchema
        # Pre-build indexes for fast matching
        self._table_tokens: Dict[str, Set[str]] = {}
        self._column_tokens: Dict[str, Dict[str, Set[str]]] = {}  # table -> column -> tokens
        self._column_labels: Dict[str, Dict[str, str]] = {}  # table -> column -> human label
        self._build_indexes()

    def _build_indexes(self) -> None:
        for table_name in self.catalog.tables:
            self._table_tokens[table_name] = self._tokenize_name(table_name)
            for col in self.catalog.columns_for(table_name):
                self._column_tokens.setdefault(table_name, {})[col] = self._tokenize_name(col)
                self._column_labels.setdefault(table_name, {})[col] = col.replace("_", " ")

    @staticmethod
    def _tokenize_name(name: str) -> Set[str]:
        """Tokenize a database identifier into expanded lowercase tokens."""
        # Replace underscores and split camelCase
        text = re.sub(r"_+", " ", name)
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        tokens = set()
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            tokens.add(token)
            expanded = _expand_abbreviation(token)
            if expanded != token:
                tokens.add(expanded)
            singular = _singularize(token)
            if singular != token:
                tokens.add(singular)
        return tokens

    def match_tables(self, question: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Return tables ranked by relevance to the question."""
        q_tokens = set(_tokenize(question))
        # Also expand abbreviations and singularize question tokens
        expanded_q = set()
        for t in q_tokens:
            expanded_q.add(t)
            expanded_q.add(_expand_abbreviation(t))
            expanded_q.add(_singularize(t))
        q_tokens = expanded_q

        scored: List[Tuple[float, str]] = []
        for table_name, table_tok in self._table_tokens.items():
            # Token overlap score
            overlap = len(q_tokens & table_tok)
            if overlap == 0:
                # Try substring matching on the original question
                singular = _singularize(table_name)
                if singular in question.lower() or table_name in question.lower():
                    overlap = 1

            if overlap > 0:
                # Precision: what fraction of question tokens match
                precision = overlap / max(len(q_tokens), 1)
                # Coverage: what fraction of table tokens match
                coverage = overlap / max(len(table_tok), 1)
                score = (precision * 0.5) + (coverage * 0.3) + (overlap * 0.2)
                scored.append((score, table_name))

        scored.sort(reverse=True)
        return [(table, score) for score, table in scored[:limit]]

    def match_columns(
        self, question: str, table: str, limit: int = 10
    ) -> List[Tuple[str, float]]:
        """Return columns from a table ranked by relevance to the question."""
        q_tokens = set(_tokenize(question))
        expanded_q = set()
        for t in q_tokens:
            expanded_q.add(t)
            expanded_q.add(_expand_abbreviation(t))
            expanded_q.add(_singularize(t))
        q_tokens = expanded_q

        col_tokens = self._column_tokens.get(table, {})
        scored: List[Tuple[float, str]] = []
        for col, col_tok in col_tokens.items():
            overlap = len(q_tokens & col_tok)
            if overlap == 0:
                # Substring fallback
                col_name_clean = col.lower().replace("_", " ")
                for qt in q_tokens:
                    if len(qt) >= 3 and qt in col_name_clean:
                        overlap += 0.5
                    if len(qt) >= 3 and qt in col.lower():
                        overlap += 0.5

            if overlap > 0:
                precision = overlap / max(len(q_tokens), 1)
                coverage = overlap / max(len(col_tok), 1)
                score = (precision * 0.5) + (coverage * 0.3) + (overlap * 0.2)
                scored.append((score, col))

        scored.sort(reverse=True)
        return [(col, score) for score, col in scored[:limit]]

    def find_best_table(self, question: str) -> Optional[str]:
        """Find the single best matching table."""
        matches = self.match_tables(question, limit=1)
        return matches[0][0] if matches else None

    def find_best_column(self, question: str, table: str) -> Optional[str]:
        """Find the single best matching column in a table."""
        matches = self.match_columns(question, table, limit=1)
        return matches[0][0] if matches else None

    def find_amount_columns(self, question: str, table: str) -> List[str]:
        """Find columns that likely represent monetary/numeric amounts."""
        numeric_types = {
            "integer", "bigint", "smallint", "numeric", "decimal",
            "real", "double precision", "money",
        }
        candidates: List[Tuple[float, str]] = []
        for col in self.catalog.columns_for(table):
            col_type = self.catalog.get_column_type(table, col).lower()
            is_numeric = col_type in numeric_types or any(
                tok in col_type for tok in ("int", "numeric", "decimal", "real", "double", "money")
            )
            if not is_numeric:
                continue
            if self.catalog.is_sensitive(col):
                continue
            # Skip ID columns
            if col.endswith("_id") or col == "id":
                continue

            # Score by question relevance
            q_tokens = set(_tokenize(question))
            col_tokens = self._column_tokens.get(table, {}).get(col, set())
            overlap = len(q_tokens & col_tokens)

            # Also check if the column name suggests a monetary value
            money_hints = {
                "amount", "price", "cost", "salary", "wage", "revenue",
                "expense", "budget", "total", "value", "payment", "fee",
                "charge", "rate", "discount", "tax", "margin", "profit",
                "balance", "income", "bonus", "commission", "unit_price",
                "discount", "total_amount", "sub_total", "grand_total",
            }
            hint_score = 2.0 if any(h in col.lower() for h in money_hints) else 0.0

            score = overlap + hint_score
            candidates.append((score, col))

        candidates.sort(reverse=True)
        return [col for _, col in candidates]

    def find_name_columns(self, table: str) -> List[str]:
        """Find columns likely to contain human-readable names/labels."""
        name_hints = {
            "name", "title", "label", "description", "subject",
            "company_name", "employee_name", "customer_name",
            "product_name", "department_name", "full_name",
            "first_name", "last_name", "username",
        }
        candidates: List[str] = []
        columns = self.catalog.columns_for(table)

        # Exact matches first
        for col in columns:
            if col.lower() in name_hints:
                candidates.append(col)

        # Columns ending with _name
        for col in columns:
            if col not in candidates and col.endswith("_name"):
                candidates.append(col)

        # Columns containing "name" or "title"
        for col in columns:
            if col not in candidates and ("name" in col.lower() or "title" in col.lower()):
                candidates.append(col)

        return candidates

    def find_status_columns(self, table: str) -> List[str]:
        """Find columns that likely contain status values."""
        candidates: List[str] = []
        for col in self.catalog.columns_for(table):
            if "status" in col.lower() or "state" in col.lower():
                candidates.append(col)
        return candidates

    def build_entity_map(self, question: str) -> Dict[str, Optional[str]]:
        """Build a complete entity mapping from question to schema.

        Returns a dict like:
        {
            "table": "<matched_table>",
            "name_column": "<best_name_column>",
            "amount_column": "<best_amount_column>",
            "status_column": "<best_status_column>",
        }
        """
        table = self.find_best_table(question)
        if not table:
            return {"table": None, "name_column": None, "amount_column": None, "status_column": None}

        name_cols = self.find_name_columns(table)
        amount_cols = self.find_amount_columns(question, table)
        status_cols = self.find_status_columns(table)

        return {
            "table": table,
            "name_column": name_cols[0] if name_cols else None,
            "amount_column": amount_cols[0] if amount_cols else None,
            "status_column": status_cols[0] if status_cols else None,
        }

    def find_two_table_pair(self, question: str) -> Optional[Tuple[str, str]]:
        """Find a pair of tables mentioned in the question (for joins).

        Returns (measure_table, group_table) where measure_table has numeric
        columns and group_table has name columns.
        """
        matches = self.match_tables(question, limit=4)
        if len(matches) < 2:
            return None

        # Try all pairs
        best_pair: Optional[Tuple[str, str]] = None
        best_score = -1.0

        for i, (t1, s1) in enumerate(matches):
            for t2, s2 in matches[i + 1:]:
                # Check if they can be joined
                path = self.catalog.join_path(t1, t2)
                if path is None:
                    continue

                # Prefer pair where one table has numeric columns (measure)
                # and the other has name columns (group)
                t1_amounts = bool(self.find_amount_columns(question, t1))
                t1_names = bool(self.find_name_columns(t1))
                t2_amounts = bool(self.find_amount_columns(question, t2))
                t2_names = bool(self.find_name_columns(t2))

                if t1_amounts and t2_names:
                    pair = (t1, t2)
                elif t2_amounts and t1_names:
                    pair = (t2, t1)
                else:
                    pair = (t1, t2)

                score = s1 + s2
                if score > best_score:
                    best_score = score
                    best_pair = pair

        return best_pair

    def infer_metric_type(self, question: str) -> str:
        """Infer what kind of metric the user wants: sum, avg, count, min, max."""
        q = question.lower()

        if any(t in q for t in ("average", "avg", "mean")):
            return "AVG"
        if any(t in q for t in ("maximum", "max", "highest", "most", "top", "largest")):
            return "MAX"
        if any(t in q for t in ("minimum", "min", "lowest", "least", "smallest")):
            return "MIN"
        if any(t in q for t in ("count", "how many", "number of")):
            return "COUNT"
        if any(t in q for t in ("total", "sum", "overall")):
            return "SUM"
        # Default heuristic
        return "SUM"

    def is_grouping_question(self, question: str) -> bool:
        """Check if the question asks for grouped/broken-down results."""
        q = question.lower()
        return any(t in q for t in (
            "each", "per ", "by ", "group", "breakdown",
            "every", "across", "distribute",
        ))

    def is_ranking_question(self, question: str) -> bool:
        """Check if the question asks for a ranked/highest/lowest result."""
        q = question.lower()
        return any(t in q for t in (
            "highest", "lowest", "most", "least", "top", "bottom",
            "which .* has", "which .* have", "which .* is",
            "biggest", "smallest", "best", "worst", "largest", "smallest",
        ))

    def is_calculation_question(self, question: str) -> bool:
        """Check if the question asks for a calculation across tables."""
        q = question.lower()
        return any(t in q for t in (
            "minus", "compare", "difference", "vs", "versus",
            "subtract", "deduct", "margin", "net",
        ))
