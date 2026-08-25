from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WebSearchResult:
    """A single web search result."""

    title: str
    url: str
    snippet: str


@dataclass
class WebSearchResponse:
    """Structured response from web search."""

    query: str
    results: List[WebSearchResult] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.results) > 0


class WebSearchService:
    """Web search using DuckDuckGo (free, no API key required).

    Falls back gracefully when the search library is unavailable or the
    network request fails.  The chat server must never crash because of
    a web search failure.
    """

    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[1]
        env_path = root / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_path, override=False)
            except ImportError:
                pass

        self.enabled = os.getenv("WEB_SEARCH_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._client = None

    def _get_client(self):
        """Lazy-load the DuckDuckGo search client."""
        if self._client is not None:
            return self._client
        try:
            from ddgs import DDGS

            self._client = DDGS()
            return self._client
        except ImportError:
            pass
        try:
            from duckduckgo_search import DDGS

            self._client = DDGS()
            return self._client
        except ImportError:
            return None

    def search(self, query: str, max_results: int = 5) -> WebSearchResponse:
        """Run a web search and return structured results.

        Never raises — always returns a WebSearchResponse with either
        results or an error message.
        """
        if not self.enabled:
            return WebSearchResponse(
                query=query, error="Web search is disabled (WEB_SEARCH_ENABLED=false)."
            )

        if not query or not query.strip():
            return WebSearchResponse(query=query, error="Empty search query.")

        client = self._get_client()
        if client is None:
            return WebSearchResponse(
                query=query,
                error=(
                    "Web search library not installed. "
                    "Run: pip install duckduckgo-search"
                ),
            )

        try:
            raw_results = client.text(query, max_results=max_results)
        except Exception as exc:
            return WebSearchResponse(
                query=query, error=f"Web search failed: {exc}"
            )

        if not raw_results:
            return WebSearchResponse(
                query=query, error="No results found for that query."
            )

        results: List[WebSearchResult] = []
        for item in raw_results:
            title = str(item.get("title", "")).strip()
            url = str(item.get("href", "")).strip()
            snippet = str(item.get("body", "")).strip()
            if title and url:
                results.append(
                    WebSearchResult(title=title, url=url, snippet=snippet)
                )

        if not results:
            return WebSearchResponse(
                query=query, error="No usable results found."
            )

        return WebSearchResponse(query=query, results=results)

    @staticmethod
    def _clean_snippet(text: str) -> str:
        """Clean a raw web snippet into readable text.

        Removes date prefixes, source attributions, and other noise
        that makes raw web content hard to read.
        """
        if not text:
            return ""
        cleaned = text.strip()
        # Remove common date prefixes like "2 days ago -", "June 2, 2026 -"
        cleaned = re.sub(r"^\d{1,2}\s+\w+\s+\d{4}\s*-\s*", "", cleaned)
        cleaned = re.sub(r"^\w+\s+\d{1,2},?\s+\d{4}\s*-\s*", "", cleaned)
        cleaned = re.sub(r"^\d+\s+(?:day|hour|minute|week|month)s?\s+ago\s*-\s*", "", cleaned, flags=re.IGNORECASE)
        # Remove LinkedIn-style truncations
        cleaned = re.sub(r"\.\.\.\s*$", ".", cleaned)
        # Remove source attributions like "| Reuters" or "- TechCrunch"
        cleaned = re.sub(r"\s*[|]\s*\w+(?:\.com)?\s*$", "", cleaned)
        cleaned = re.sub(r"\s*-\s*\w+(?:\.com)?\s*$", "", cleaned)
        # Limit length
        if len(cleaned) > 300:
            # Cut at sentence boundary
            cut = cleaned[:300].rfind(".")
            if cut > 100:
                cleaned = cleaned[:cut + 1]
            else:
                cleaned = cleaned[:300].strip() + "..."
        return cleaned

    def build_answer(
        self,
        response: WebSearchResponse,
        category: str = "general",
        question: str = "",
    ) -> str:
        """Build a clean, focused answer from search results.

        Removes duplicates, filters irrelevant results, and produces
        a concise answer that directly addresses the user's question.
        Does NOT use any LLM — avoids hallucination.
        """
        if not response.ok:
            return response.error or "I couldn't retrieve web information."

        # Step 1: Deduplicate results by URL.
        seen_urls: set = set()
        unique_results: List[WebSearchResult] = []
        for r in response.results:
            url_norm = r.url.rstrip("/").lower()
            if url_norm not in seen_urls:
                seen_urls.add(url_norm)
                unique_results.append(r)

        # Step 2: Filter out very short or empty snippets.
        useful = [r for r in unique_results if r.snippet and len(r.snippet.strip()) > 20]

        if not useful:
            useful = unique_results  # Fall back to all unique results.

        # Step 3: Build a focused answer based on category.
        lines: List[str] = []
        if category == "weather":
            for r in useful[:2]:
                snippet = self._clean_snippet(r.snippet)
                if snippet:
                    lines.append(snippet)
        elif category == "price":
            for r in useful[:2]:
                snippet = self._clean_snippet(r.snippet)
                if snippet:
                    lines.append(snippet)
        elif category == "news":
            for r in useful[:3]:
                snippet = self._clean_snippet(r.snippet)
                if snippet:
                    lines.append(f"• **{r.title}**: {snippet}")
        elif category == "person":
            for r in useful[:2]:
                snippet = self._clean_snippet(r.snippet)
                if snippet:
                    lines.append(snippet)
        else:
            for r in useful[:3]:
                snippet = self._clean_snippet(r.snippet)
                if snippet:
                    lines.append(f"**{r.title}**: {snippet}")

        if not lines:
            return "I found some web results but could not extract useful information."

        answer = "\n\n".join(lines)
        return answer

    def status(self) -> Dict[str, Any]:
        """Return search service status (safe, no secrets)."""
        return {
            "enabled": self.enabled,
            "provider": "duckduckgo",
            "api_key_required": False,
        }
