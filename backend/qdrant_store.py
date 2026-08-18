from __future__ import annotations

import hashlib
import os
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


def _load_qdrant_env() -> None:
    # Keep credentials server-side only; load from project .env if present.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


class QdrantStore:
    """Qdrant Cloud vector store for knowledge retrieval."""

    def __init__(
        self,
        collection_name: str = "company_knowledge",
        vector_size: int = 256,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        _load_qdrant_env()
        self.url = (url or os.getenv("QDRANT_URL") or "").strip().rstrip("/")
        self.api_key = (api_key or os.getenv("QDRANT_API_KEY") or "").strip()
        if not self.url:
            raise RuntimeError("QDRANT_URL is required for Qdrant Cloud.")
        if not self.api_key:
            raise RuntimeError("QDRANT_API_KEY is required for Qdrant Cloud.")
        if self.url.startswith("http://localhost") or self.url.startswith("http://127.0.0.1"):
            raise RuntimeError("Local Qdrant is disabled. Use Qdrant Cloud credentials.")

        self.collection_name = collection_name
        self.vector_size = vector_size
        self.tls_verify = self._resolve_tls_verify()
        self.client = self._connect_with_fallback()
        self._ensure_collection()

    @staticmethod
    def _resolve_tls_verify() -> bool:
        """Resolve TLS verification mode for Qdrant Cloud.

        Python 3.14 on some Windows hosts rejects the cloud CA chain with
        'Basic Constraints of CA cert not marked critical'. Default is secure
        verify=True, with automatic fallback when that specific SSL failure occurs
        unless QDRANT_TLS_VERIFY is explicitly set.
        """
        raw = (os.getenv("QDRANT_TLS_VERIFY") or "auto").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        # auto: prefer verified TLS
        return True

    def _connect_with_fallback(self) -> QdrantClient:
        client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60,
            check_compatibility=False,
            verify=self.tls_verify,
        )
        if self.tls_verify and (os.getenv("QDRANT_TLS_VERIFY") or "auto").strip().lower() == "auto":
            try:
                client.get_collections()
                return client
            except Exception as exc:
                message = str(exc).lower()
                if "certificate" in message or "ssl" in message:
                    self.tls_verify = False
                    client = QdrantClient(
                        url=self.url,
                        api_key=self.api_key,
                        timeout=60,
                        check_compatibility=False,
                        verify=False,
                    )
                    client.get_collections()
                    return client
                raise
        return client

    def _safe_host(self) -> str:
        parsed = urlparse(self.url)
        return parsed.hostname or "<unknown-host>"

    def _ensure_collection(self) -> None:
        names = {c.name for c in self.client.get_collections().collections}
        if self.collection_name in names:
            info = self.client.get_collection(self.collection_name)
            # Recreate if existing collection has incompatible vector size.
            try:
                existing_size = info.config.params.vectors.size  # type: ignore[attr-defined]
            except Exception:
                existing_size = None
            if existing_size is not None and int(existing_size) != int(self.vector_size):
                self.reset_collection()
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=self.vector_size, distance=qmodels.Distance.COSINE),
        )

    def reset_collection(self) -> None:
        names = {c.name for c in self.client.get_collections().collections}
        if self.collection_name in names:
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=self.vector_size, distance=qmodels.Distance.COSINE),
        )

    @staticmethod
    def _point_id(doc_id: str) -> str:
        # Stable UUIDs from document ids for upserts.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id))

    def upsert_documents(self, documents: List[Dict[str, Any]], vectors: List[List[float]]) -> int:
        if len(documents) != len(vectors):
            raise ValueError("documents and vectors length mismatch")
        points = []
        for doc, vector in zip(documents, vectors):
            doc_id = str(doc.get("id") or hashlib.sha1(str(doc.get("text", "")).encode("utf-8")).hexdigest())
            payload = {
                "doc_id": doc_id,
                "text": doc.get("text", ""),
                "source": doc.get("source", "unknown"),
                "title": doc.get("title", ""),
                "metadata": doc.get("metadata") or {},
            }
            points.append(
                qmodels.PointStruct(
                    id=self._point_id(doc_id),
                    vector=vector,
                    payload=payload,
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(points)

    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: Optional[float] = 0.05,
    ) -> List[Dict[str, Any]]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            score_threshold=score_threshold,
        )
        hits = getattr(response, "points", None) or response
        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "id": payload.get("doc_id"),
                    "score": float(hit.score or 0.0),
                    "text": payload.get("text", ""),
                    "source": payload.get("source"),
                    "title": payload.get("title"),
                    "metadata": payload.get("metadata") or {},
                }
            )
        return results

    def count(self) -> int:
        info = self.client.get_collection(self.collection_name)
        return int(info.points_count or 0)

    def ping(self) -> Dict[str, Any]:
        collections = [c.name for c in self.client.get_collections().collections]
        return {
            "ok": True,
            "host": self._safe_host(),
            "collections": collections,
            "mode": "qdrant-cloud",
        }

    def status(self) -> Dict[str, Any]:
        # Never include API key or full credentialized URL.
        return {
            "collection": self.collection_name,
            "host": self._safe_host(),
            "mode": "qdrant-cloud",
            "tls_verify": self.tls_verify,
            "vector_size": self.vector_size,
            "points": self.count(),
        }
