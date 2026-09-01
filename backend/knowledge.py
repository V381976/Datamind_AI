from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.embedding_service import EmbeddingService
from backend.qdrant_store import QdrantStore
from backend.schema_catalog import DatabaseSchema


class KnowledgeService:
    """Indexes database/document text into Qdrant and retrieves semantic context.

    Fully generic — generates knowledge documents from any schema without
    hardcoded table or column names.
    """

    def __init__(self, embedding_service: EmbeddingService, store: Optional[QdrantStore] = None) -> None:
        self.embedding_service = embedding_service
        if store is not None:
            self.store = store
        else:
            try:
                self.store = QdrantStore(vector_size=embedding_service.vector_size)
            except Exception as exc:
                print(f"Warning: Qdrant store initialization failed: {exc}")
                print("Knowledge retrieval will be disabled. Chat will still work with curated answers.")
                self.store = None
        self._indexed = False

    @staticmethod
    def _extract_answers_from_text(content: str) -> List[Dict[str, str]]:
        """Extract question-answer pairs from training files.

        Training files have format:
            User: question
            Assistant: answer

        Returns a list of {"question": ..., "answer": ...} dicts.
        """
        import re
        pair_re = re.compile(
            r"^User:\s*(?P<question>.+?)\r?\nAssistant:\s*(?P<answer>.+?)"
            r"(?=\r?\n\r?\nUser:|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        pairs = []
        for match in pair_re.finditer(content):
            q = match.group("question").strip()
            a = match.group("answer").strip()
            if q and a:
                pairs.append({"question": q, "answer": a})
        return pairs

    def _load_raw_knowledge_files(self) -> List[Dict[str, Any]]:
        """Load and chunk knowledge from raw training/conversation files.

        These files contain curated Q&A pairs covering general conversation,
        AI/LLM knowledge, technical topics, trading, Hindi/Hinglish, and
        follow-up examples.  They are the primary knowledge source when no
        database is connected.

        Extracts ONLY the Assistant answers (not User: prefixes) to avoid
        raw training format leaking into responses.
        """
        docs: List[Dict[str, Any]] = []
        raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
        if not raw_dir.exists():
            return docs

        for path in sorted(raw_dir.glob("*.txt")):
            if path.name == "sample.txt":
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                continue
            if len(content) < 40:
                continue

            # Extract Q&A pairs and store answers as clean knowledge
            pairs = self._extract_answers_from_text(content)
            if pairs:
                # Chunk answers into groups of 3-5 for context
                chunk_size = 4
                for idx in range(0, len(pairs), chunk_size):
                    chunk_pairs = pairs[idx : idx + chunk_size]
                    # Build a clean text from answers only
                    answer_texts = []
                    for p in chunk_pairs:
                        # Include question as context label, but answer is the main text
                        answer_texts.append(f"{p['question']}\n{p['answer']}")
                    text = "\n\n".join(answer_texts)
                    if not text.strip():
                        continue
                    docs.append({
                        "id": f"raw:{path.name}:{idx}",
                        "title": path.stem.replace("_", " "),
                        "source": f"raw/{path.name}",
                        "text": text,
                        "metadata": {"path": str(path), "type": "raw_knowledge"},
                    })
            else:
                # Fallback: chunk raw text (for files without Q&A format)
                chunk_size = 400
                chunks: List[str] = []
                parts = content.split("\n\n")
                current = ""
                for part in parts:
                    if len(current) + len(part) + 2 > chunk_size and current:
                        chunks.append(current.strip())
                        current = part
                    else:
                        current = (current + "\n\n" + part) if current else part
                if current.strip():
                    chunks.append(current.strip())
                for idx, chunk in enumerate(chunks):
                    if not chunk:
                        continue
                    docs.append({
                        "id": f"raw:{path.name}:{idx}",
                        "title": path.stem.replace("_", " "),
                        "source": f"raw/{path.name}",
                        "text": chunk,
                        "metadata": {"path": str(path), "type": "raw_knowledge"},
                    })
        return docs

    def build_documents_from_database(self, connection, schema: Optional[DatabaseSchema] = None) -> List[Dict[str, Any]]:
        """Generate knowledge documents from raw files and optionally a database.

        Always indexes raw knowledge/training files so the knowledge system
        works independently of any database connection.

        When a database connection + schema are provided, also indexes
        table summaries, sample rows, and aggregate snapshots.
        """
        docs: List[Dict[str, Any]] = []

        # ── Always: raw knowledge files (conversation, technical, AI, etc.) ──
        docs.extend(self._load_raw_knowledge_files())

        # ── Optional: database-specific documents ──
        if connection is not None and schema is not None:
            try:
                with connection.cursor() as cursor:
                    for table_name, table_info in schema.tables.items():
                        col_names = schema.safe_columns(table_name)
                        col_list = ", ".join(col_names[:20])
                        table_desc = table_info.comment or f"Table '{table_name}'"
                        overview_text = (
                            f"Table: {table_name}. {table_desc}. "
                            f"Columns: {col_list}. "
                            f"Contains {len(table_info.columns)} columns total."
                        )
                        if table_info.primary_keys:
                            overview_text += f" Primary key: {', '.join(table_info.primary_keys)}."
                        docs.append({
                            "id": f"table:{table_name}:overview",
                            "title": f"Table: {table_name}",
                            "source": f"schema.{table_name}",
                            "text": overview_text,
                            "metadata": {"table": table_name, "type": "overview"},
                        })

                        # Row-level documents (sample up to 50 rows)
                        try:
                            name_col = schema.find_name_column(table_name)
                            id_col = table_info.primary_keys[0] if table_info.primary_keys else None
                            amount_col = schema.find_amount_column(table_name)
                            select_parts = []
                            if id_col and id_col in col_names:
                                select_parts.append(id_col)
                            if name_col and name_col in col_names and name_col != id_col:
                                select_parts.append(name_col)
                            if amount_col and amount_col in col_names and amount_col not in (id_col, name_col):
                                select_parts.append(amount_col)
                            for col in col_names:
                                if col not in select_parts and len(select_parts) < 8:
                                    select_parts.append(col)
                            if not select_parts:
                                select_parts = col_names[:6]
                            quoted_cols = ", ".join(f'"{c}"' for c in select_parts)
                            cursor.execute(f'SELECT {quoted_cols} FROM "{table_name}" LIMIT 50')
                            rows = cursor.fetchall()
                            for row in rows:
                                row_dict = {}
                                for i, col in enumerate(select_parts):
                                    val = row[i] if i < len(row) else None
                                    if hasattr(val, "isoformat"):
                                        val = val.isoformat()
                                    elif type(val).__name__ == "Decimal":
                                        val = float(val)
                                    row_dict[col] = val
                                display_name = row_dict.get(name_col) if name_col else None
                                row_id = row_dict.get(id_col) if id_col else None
                                doc_title = f"{table_name}: {display_name or row_id or 'row'}"
                                parts = []
                                for k, v in row_dict.items():
                                    if v is not None:
                                        parts.append(f"{k.replace('_', ' ')}: {v}")
                                text = f"Record in {table_name}: {'. '.join(parts)}"
                                doc_id = f"row:{table_name}:{row_id}" if row_id else f"row:{table_name}:{hash(str(row_dict)) % 100000}"
                                docs.append({
                                    "id": doc_id,
                                    "title": str(doc_title),
                                    "source": f"data.{table_name}",
                                    "text": text,
                                    "metadata": {"table": table_name, "row_id": row_id},
                                })
                        except Exception:
                            pass

                        # Aggregate snapshot for tables with numeric columns
                        numeric_cols = schema.find_numeric_columns(table_name)
                        if numeric_cols:
                            try:
                                agg_parts = []
                                for col in numeric_cols[:5]:
                                    quoted = f'"{col}"'
                                    agg_parts.append(f"SUM({quoted}) AS total_{col}")
                                    agg_parts.append(f"COUNT(*) AS count_{col}")
                                agg_sql = f"SELECT {', '.join(agg_parts)} FROM \"{table_name}\""
                                cursor.execute(agg_sql)
                                agg_row = cursor.fetchone()
                                if agg_row:
                                    parts = []
                                    for i, col in enumerate(numeric_cols[:5]):
                                        total_val = agg_row[i * 2] if i * 2 < len(agg_row) else 0
                                        count_val = agg_row[i * 2 + 1] if i * 2 + 1 < len(agg_row) else 0
                                        if total_val is not None:
                                            parts.append(f"total {col.replace('_', ' ')}: {total_val}")
                                        parts.append(f"total {table_name} records: {count_val}")
                                    text = f"Aggregate summary for {table_name}: {'. '.join(parts)}"
                                    docs.append({
                                        "id": f"agg:{table_name}",
                                        "title": f"Aggregate: {table_name}",
                                        "source": f"aggregate.{table_name}",
                                        "text": text,
                                        "metadata": {"table": table_name, "type": "aggregate"},
                                    })
                            except Exception:
                                pass
            except Exception:
                pass

        return docs

    def index_database(self, connection, schema: Optional[DatabaseSchema] = None, force: bool = False) -> Dict[str, Any]:
        if self.store is None:
            return {"indexed": False, "points": 0, "reason": "qdrant_unavailable"}
        if self._indexed and not force and self.store.count() > 0:
            return {"indexed": False, "points": self.store.count(), "reason": "already_indexed"}
        documents = self.build_documents_from_database(connection, schema=schema)
        if not documents:
            return {"indexed": False, "points": 0, "reason": "no_documents"}
        if force or self.store.count() == 0:
            self.store.reset_collection()
        vectors = self.embedding_service.embed_texts([doc["text"] for doc in documents])
        count = self.store.upsert_documents(documents, vectors)
        self._indexed = True
        return {"indexed": True, "points": count}

    def index_knowledge_files(self, force: bool = False) -> Dict[str, Any]:
        """Index raw knowledge files without requiring a database connection.

        This allows the knowledge/retrieval system to work even when no
        database is connected.
        """
        if self.store is None:
            return {"indexed": False, "points": 0, "reason": "qdrant_unavailable"}
        if self._indexed and not force and self.store.count() > 0:
            return {"indexed": False, "points": self.store.count(), "reason": "already_indexed"}
        documents = self._load_raw_knowledge_files()
        if not documents:
            return {"indexed": False, "points": 0, "reason": "no_documents"}
        if force or self.store.count() == 0:
            self.store.reset_collection()
        vectors = self.embedding_service.embed_texts([doc["text"] for doc in documents])
        count = self.store.upsert_documents(documents, vectors)
        self._indexed = True
        return {"indexed": True, "points": count}

    def retrieve(self, question: str, limit: int = 5) -> List[Dict[str, Any]]:
        if self.store is None:
            return []
        vector = self.embedding_service.embed_question(question)
        hits = self.store.search(vector, limit=max(limit * 3, 9))

        q = question.lower()

        def rank(hit: Dict[str, Any]) -> float:
            score = float(hit.get("score") or 0.0)
            source = str(hit.get("source") or "")
            text = str(hit.get("text") or "").lower()
            title = str(hit.get("title") or "").lower()

            # Boost schema/data sources
            if source.startswith("schema.") or source.startswith("data."):
                score += 0.35

            # Generic keyword boosting — match any table/column name from source
            # No hardcoded entity names
            source_table = source.split(".")[-1] if "." in source else ""
            if source_table and source_table in q:
                score += 0.4

            # Boost aggregate docs for summary-type questions
            if any(t in q for t in ("summary", "overview", "total", "snapshot")):
                if source.startswith("aggregate.") or source.startswith("schema."):
                    score += 0.3

            return score

        hits = sorted(hits, key=rank, reverse=True)
        return hits[:limit]

    @staticmethod
    def _clean_retrieved_text(text: str) -> str:
        """Remove training format artifacts from retrieved text.

        The raw knowledge files contain User:/Assistant: pairs.  When
        retrieved as knowledge, these should be cleaned.
        """
        import re
        if not text:
            return text
        # Remove leading "User: ..." lines
        cleaned = re.sub(r"^User:\s*.+?\n", "", text, flags=re.MULTILINE)
        # Remove "Assistant: " prefix
        cleaned = re.sub(r"^Assistant:\s*", "", cleaned, flags=re.MULTILINE)
        # Remove consecutive newlines from stripped lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def answer_from_retrieval(self, question: str, hits: List[Dict[str, Any]]) -> Optional[str]:
        if not hits:
            return None
        top = hits[0]
        q = question.lower()

        if any(t in q for t in ("summary", "tell me about", "about the", "overview")):
            overview_hits = [h for h in hits if h.get("metadata", {}).get("type") == "overview"]
            data_hits = [h for h in hits if h.get("metadata", {}).get("type") != "overview"]
            selected = overview_hits[:1] + data_hits[:2]
            context = " ".join(h.get("text", "") for h in selected if h.get("text"))
            return self._clean_retrieved_text(context or top.get("text"))

        raw_text = top.get("text", "")
        cleaned = self._clean_retrieved_text(raw_text)

        if "explain" in q:
            return f"{cleaned}"
        if "why" in q:
            return cleaned
        return cleaned

    def reindex(self, connection, schema: Optional[DatabaseSchema] = None) -> Dict[str, Any]:
        if self.store is None:
            return {"indexed": False, "points": 0, "reason": "qdrant_unavailable"}
        return self.index_database(connection, schema=schema, force=True)
