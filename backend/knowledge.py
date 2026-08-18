from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.embedding_service import EmbeddingService
from backend.qdrant_store import QdrantStore


class KnowledgeService:
    """Indexes database/document text into Qdrant and retrieves semantic context."""

    def __init__(self, embedding_service: EmbeddingService, store: Optional[QdrantStore] = None) -> None:
        self.embedding_service = embedding_service
        self.store = store or QdrantStore(vector_size=embedding_service.vector_size)
        self._indexed = False

    def build_documents_from_database(self, connection) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        if connection is None:
            return docs

        with connection.cursor() as cursor:
            # Company profiles
            try:
                cursor.execute(
                    """
                    SELECT company_id, company_name, industry, founded_date, headquarters_city,
                           headquarters_country, website, email, phone, description
                    FROM companies
                    """
                )
                for row in cursor.fetchall():
                    (
                        company_id,
                        name,
                        industry,
                        founded,
                        city,
                        country,
                        website,
                        email,
                        phone,
                        description,
                    ) = row
                    text = (
                        f"Company profile: {name}. Industry: {industry}. "
                        f"Founded: {founded}. Headquarters: {city}, {country}. "
                        f"Website: {website}. Email: {email}. Phone: {phone}. "
                        f"Description: {description}"
                    )
                    docs.append(
                        {
                            "id": f"company:{company_id}",
                            "title": f"Company: {name}",
                            "source": "postgresql.companies",
                            "text": text,
                            "metadata": {"table": "companies", "company_id": company_id},
                        }
                    )
            except Exception:
                pass

            # Departments
            try:
                cursor.execute(
                    """
                    SELECT d.department_id, d.department_name, d.budget, d.headcount, c.company_name
                    FROM departments d
                    LEFT JOIN companies c ON c.company_id = d.company_id
                    """
                )
                for dept_id, dept_name, budget, headcount, company_name in cursor.fetchall():
                    text = (
                        f"Department: {dept_name} at {company_name or 'the company'}. "
                        f"Budget: {budget}. Headcount: {headcount}. "
                        f"This department supports company operations and delivery."
                    )
                    docs.append(
                        {
                            "id": f"department:{dept_id}",
                            "title": f"Department: {dept_name}",
                            "source": "postgresql.departments",
                            "text": text,
                            "metadata": {"table": "departments", "department_id": dept_id},
                        }
                    )
            except Exception:
                pass

            # Products
            try:
                cursor.execute(
                    """
                    SELECT product_id, product_name, category, unit_price, stock_quantity, status, release_date
                    FROM products
                    """
                )
                for product_id, product_name, category, price, stock, status, release_date in cursor.fetchall():
                    text = (
                        f"Product: {product_name}. Category: {category}. "
                        f"Unit price: {price}. Stock: {stock}. Status: {status}. "
                        f"Released: {release_date}."
                    )
                    docs.append(
                        {
                            "id": f"product:{product_id}",
                            "title": f"Product: {product_name}",
                            "source": "postgresql.products",
                            "text": text,
                            "metadata": {"table": "products", "product_id": product_id},
                        }
                    )
            except Exception:
                pass

            # High-level business snapshot from aggregates (read-only facts, not hardcoded answers)
            try:
                cursor.execute("SELECT COUNT(*) FROM employees")
                employee_count = cursor.fetchone()[0]
                cursor.execute("SELECT COALESCE(SUM(amount),0) FROM revenues")
                total_revenue = cursor.fetchone()[0]
                cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses")
                total_expenses = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM customers")
                customer_count = cursor.fetchone()[0]
                text = (
                    f"Business snapshot: the company currently has {employee_count} employees, "
                    f"{customer_count} customers, total recorded revenue {total_revenue}, "
                    f"and total recorded expenses {total_expenses}."
                )
                docs.append(
                    {
                        "id": "snapshot:business",
                        "title": "Business snapshot",
                        "source": "postgresql.aggregates",
                        "text": text,
                        "metadata": {"table": "aggregates"},
                    }
                )
            except Exception:
                pass

        # Optional curated knowledge files only (avoid training corpora pollution).
        root = Path(__file__).resolve().parents[1]
        knowledge_dir = root / "data" / "knowledge"
        if knowledge_dir.exists():
            for path in knowledge_dir.rglob("*.txt"):
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if len(content) < 40:
                    continue
                chunk_size = 500
                for idx in range(0, min(len(content), 4000), chunk_size):
                    chunk = content[idx : idx + chunk_size].strip()
                    if not chunk:
                        continue
                    docs.append(
                        {
                            "id": f"file:{path.name}:{idx}",
                            "title": path.stem,
                            "source": f"file:{path.as_posix()}",
                            "text": chunk,
                            "metadata": {"path": str(path)},
                        }
                    )
        return docs

    def index_database(self, connection, force: bool = False) -> Dict[str, Any]:
        if self._indexed and not force and self.store.count() > 0:
            return {"indexed": False, "points": self.store.count(), "reason": "already_indexed"}
        documents = self.build_documents_from_database(connection)
        if not documents:
            return {"indexed": False, "points": 0, "reason": "no_documents"}
        if force or self.store.count() == 0:
            self.store.reset_collection()
        vectors = self.embedding_service.embed_texts([doc["text"] for doc in documents])
        count = self.store.upsert_documents(documents, vectors)
        self._indexed = True
        return {"indexed": True, "points": count}

    def retrieve(self, question: str, limit: int = 5) -> List[Dict[str, Any]]:
        vector = self.embedding_service.embed_question(question)
        hits = self.store.search(vector, limit=max(limit * 3, 9))
        q = question.lower()

        def rank(hit: Dict[str, Any]) -> float:
            score = float(hit.get("score") or 0.0)
            source = str(hit.get("source") or "")
            text = str(hit.get("text") or "").lower()
            title = str(hit.get("title") or "").lower()
            if source.startswith("postgresql."):
                score += 0.35
            if "company" in q and ("company" in source or "company" in title or "company profile" in text):
                score += 0.4
            if "department" in q or "engineering" in q:
                if "department" in source or "department" in title:
                    score += 0.45
                if "engineering" in text or "engineering" in title:
                    score += 0.35
            if "product" in q:
                if "products" in source or "product" in title or text.startswith("product:"):
                    score += 0.8
                if "snapshot" in source or "companies" in source:
                    score -= 0.4
            if "revenue" in q and ("revenue" in text or "snapshot" in source):
                score += 0.25
            return score

        hits = sorted(hits, key=rank, reverse=True)
        return hits[:limit]

    def answer_from_retrieval(self, question: str, hits: List[Dict[str, Any]]) -> Optional[str]:
        if not hits:
            return None
        top = hits[0]
        q = question.lower()
        if "product" in q and any(token in q for token in ("describe", "list", "show", "about", "what")):
            product_hits = [
                h
                for h in hits
                if "products" in str(h.get("source", ""))
                or str(h.get("title", "")).lower().startswith("product")
                or str(h.get("text", "")).lower().startswith("product:")
            ]
            if not product_hits:
                # Broaden search window once more for product docs.
                vector = self.embedding_service.embed_question(question)
                broader = self.store.search(vector, limit=20, score_threshold=0.0)
                product_hits = [
                    h
                    for h in broader
                    if "products" in str(h.get("source", ""))
                    or str(h.get("text", "")).lower().startswith("product:")
                ]
            if product_hits:
                lines = [h.get("text", "").strip() for h in product_hits if h.get("text")]
                return "Here are the products:\n- " + "\n- ".join(lines)

        if "summary" in q or "tell me about" in q or "about the company" in q:
            company_hits = [h for h in hits if str(h.get("source", "")).startswith("postgresql.companies")]
            snapshot_hits = [h for h in hits if "snapshot" in str(h.get("source", ""))]
            selected = company_hits[:1] + snapshot_hits[:1] + [h for h in hits if h not in company_hits + snapshot_hits][:1]
            context = " ".join(h.get("text", "") for h in selected if h.get("text"))
            return context or top.get("text")
        if "explain" in q:
            return f"Based on available knowledge: {top.get('text')}"
        if "why" in q:
            if "month" in q or "lower" in q or "higher" in q:
                related = top.get("text")
                if str(top.get("source", "")).startswith("postgresql."):
                    return (
                        "I do not have enough month-over-month causal data to explain that change. "
                        f"Related available facts: {related}"
                    )
                return "I do not have enough month-over-month causal data to explain that change from the connected database."
            return (
                "I found related information, but not a definitive causal explanation. "
                f"Relevant facts: {top.get('text')}"
            )
        return top.get("text")

    def reindex(self, connection) -> Dict[str, Any]:
        return self.index_database(connection, force=True)
