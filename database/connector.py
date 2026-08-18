from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

from config import DEFAULT_CONFIG


def _load_project_env() -> None:
    candidate_roots = [
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    ]
    seen = set()
    for root in candidate_roots:
        if root in seen:
            continue
        seen.add(root)
        env_file = root / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
            for key in ("POSTGRES_DATABASE_URL", "DATABASE_URL", "MONGODB_URI"):
                value = os.getenv(key)
                if value and value.startswith(("postgresql://", "postgres://")):
                    os.environ.setdefault("POSTGRES_DATABASE_URL", value)
                    os.environ.setdefault("DATABASE_URL", value)
                    return
            return


_load_project_env()


class DatabaseConnector:
    """Backend-only PostgreSQL connector with strict validation and read-only semantics."""

    SUPPORTED_DRIVERS = {"postgresql", "postgres", "postgresql+psycopg", "postgresql+psycopg2"}

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = (
            database_url
            or os.getenv("POSTGRES_DATABASE_URL")
            or DEFAULT_CONFIG.database_url
        )
        self.database_name: Optional[str] = None
        self._connection = None
        self._validated = False

    @staticmethod
    def _safe_url_for_logging(url: Optional[str]) -> str:
        if not url:
            return "<not set>"
        parsed = urlparse(url)
        host = parsed.hostname or "<unknown-host>"
        port = f":{parsed.port}" if parsed.port else ""
        user = parsed.username or "<user>"
        return f"{parsed.scheme}://{user}:*****@{host}{port}{parsed.path or ''}"

    def validate_url(self, database_url: Optional[str] = None) -> str:
        url = database_url or self.database_url
        if url is None or (isinstance(url, str) and url.strip() == ""):
            raise ValueError("PostgreSQL connection URL is required. Set POSTGRES_DATABASE_URL.")

        parsed = urlparse(url)
        if parsed.scheme.lower() not in self.SUPPORTED_DRIVERS:
            raise ValueError(f"Unsupported database type: {parsed.scheme or 'unknown'}")

        if not parsed.hostname:
            raise ValueError("PostgreSQL URL must include a hostname.")

        self.database_url = url
        self._validated = True
        return url

    def connect(self) -> Any:
        url = self.validate_url()

        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PostgreSQL support requires psycopg to be installed.") from exc

        try:
            connection = psycopg.connect(
                url,
                connect_timeout=10,
                autocommit=True,
            )
        except Exception as exc:  # pragma: no cover - database failure path
            raise ConnectionError(f"PostgreSQL connection failed for {self._safe_url_for_logging(url)}") from exc

        self._connection = connection
        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                row = cursor.fetchone()
                if row:
                    self.database_name = row[0]
        except Exception:
            self.database_name = None

        return self._connection

    def get_database(self) -> Any:
        if self._connection is None or self._connection.closed:
            self._connection = None
            self.connect()
        return self._connection

    def ensure_healthy_connection(self) -> Any:
        """Return a usable connection, reconnecting after pooler/session failures."""
        try:
            connection = self.get_database()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return connection
        except Exception:
            self.close()
            return self.connect()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self.database_name = None

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "url_present": bool(self.database_url),
            "validated": self._validated,
            "database_type": "postgresql" if self.database_url and urlparse(self.database_url).scheme.lower() in self.SUPPORTED_DRIVERS else None,
            "host": urlparse(self.database_url).hostname if self.database_url else None,
            "connected": self._connection is not None,
            "database_name": self.database_name,
        }
