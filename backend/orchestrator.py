from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.answer_formatter import format_answer
from backend.custom_llm import CustomLLMService
from backend.embedding_service import EmbeddingService
from backend.knowledge import KnowledgeService
from backend.query_planner import QueryPlanner
from backend.router import ConversationRouter
from backend.safe_sql import SafeSQLExecutor
from backend.context_resolver import build_web_search_query, extract_search_category
from backend.schema_catalog import load_schema_catalog, load_schema_catalog_no_cache, DatabaseSchema
from backend.web_search import WebSearchService


class ChatOrchestrator:
    """Routes chat turns through Custom LLM, PostgreSQL, or Qdrant retrieval."""

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.knowledge_service = KnowledgeService(self.embedding_service)
        self.custom_llm = CustomLLMService()
        self.web_search = WebSearchService()
        self._knowledge_ready = False
        self._current_schema: Optional[DatabaseSchema] = None

    def ensure_knowledge_index(self, connection=None) -> Dict[str, Any]:
        """Ensure the knowledge index is populated.

        If a database connection is available, indexes both raw knowledge files
        and database documents.  If no connection is available, indexes only
        the raw knowledge/training files so the system still works.
        """
        try:
            if self.knowledge_service.store is None:
                return {"ready": False, "points": 0, "reason": "qdrant_unavailable"}
            if self._knowledge_ready and self.knowledge_service.store.count() > 0:
                return {"ready": True, "points": self.knowledge_service.store.count()}
            # Force rebuild once per process start so stale/training vectors are replaced.
            if connection is not None:
                schema = self._get_or_discover_schema(connection)
                result = self.knowledge_service.index_database(connection, schema=schema, force=True)
            else:
                result = self.knowledge_service.index_knowledge_files(force=True)
            self._knowledge_ready = bool(result.get("points", 0) > 0)
            return result
        except Exception as exc:
            print(f"ensure_knowledge_index failed (Qdrant may be unavailable): {exc}")
            self._knowledge_ready = False
            return {"ready": False, "points": 0, "error": str(exc)}

    def _get_or_discover_schema(self, connection) -> DatabaseSchema:
        """Get cached schema or discover fresh."""
        if self._current_schema is not None and connection is not None:
            return self._current_schema
        if connection is not None:
            self._current_schema = load_schema_catalog(connection)
            return self._current_schema
        return DatabaseSchema()

    def invalidate_schema_cache(self) -> None:
        """Invalidate the cached schema so next request re-discovers."""
        self._current_schema = None

    def _sanitize(self, result: Any) -> Any:
        if isinstance(result, dict):
            return {k: self._sanitize(v) for k, v in result.items()}
        if isinstance(result, list):
            return [self._sanitize(v) for v in result]
        if isinstance(result, (str, int, float, bool)) or result is None:
            return result
        return str(result)

    def _history_context(self, history: List[Dict[str, Any]], limit: int = 6) -> str:
        parts = []
        for item in history[-limit:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def _handle_memory(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        prior_user = [m for m in history if m.get("role") == "user"]
        # Exclude the just-added current question (last user message).
        previous = prior_user[:-1]
        if not previous:
            answer = "I do not have an earlier question in this conversation yet."
        else:
            last = previous[-1].get("content", "")
            answer = f'Previously, you asked: "{last}"'
        return {
            "answer": answer,
            "route": "memory",
            "tool": "conversation_history",
            "table": None,
            "result": {"previous_questions": [m.get("content") for m in previous[-5:]]},
            "plan": {"tool": "conversation_history", "intent": "memory"},
            "llm": "custom-gpt",
            "llm_used": False,
            "retrieval": [],
        }

    def _handle_general(self, message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        context = self._history_context(history)
        prior_user = [m.get("content", "") for m in history if m.get("role") == "user"]

        # First, check if the message itself has a curated answer (highest priority)
        curated = self.custom_llm.curated_answers.find(message)
        if curated:
            return {
                "answer": curated.answer,
                "route": "general",
                "tool": "curated",
                "table": None,
                "result": {"source": curated.source},
                "plan": {"tool": "curated", "intent": "general"},
                "llm": "custom-gpt",
                "llm_used": False,
                "retrieval": [],
            }

        # Find the topic anchor — the most recent substantive question,
        # not just the immediately previous user message.
        previous_message = prior_user[-2] if len(prior_user) >= 2 else None
        if previous_message and not self.custom_llm.curated_answers.find(previous_message):
            # Walk backwards to find a message with a curated answer
            for candidate in reversed(prior_user[:-1]):
                if self.custom_llm.curated_answers.find(candidate):
                    previous_message = candidate
                    break

        # Also use context_resolver's topic anchor for better follow-up detection
        from backend.context_resolver import find_topic_anchor, is_follow_up
        if is_follow_up(message) and history:
            topic_anchor = find_topic_anchor(history)
            if topic_anchor and not previous_message:
                previous_message = topic_anchor

        result = self.custom_llm.answer_general(
            message,
            context=context,
            previous_message=previous_message,
        )
        return {
            "answer": result["answer"],
            "route": "general",
            "tool": "custom_llm",
            "table": None,
            "result": {"fallback": result.get("fallback")},
            "plan": {"tool": "custom_llm", "intent": "general"},
            "llm": "custom-gpt",
            "llm_used": bool(result.get("llm_used")),
            "retrieval": [],
        }

    def _handle_database(self, message: str, connection, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if connection is None:
            return {
                "answer": "No database is connected, so I cannot run structured SQL for that question.",
                "route": "database",
                "tool": "unsupported",
                "table": None,
                "result": {},
                "plan": {"tool": "unsupported", "intent": "database", "reason": "no_database"},
                "llm": "custom-gpt",
                "llm_used": False,
                "retrieval": [],
                "unsupported": True,
            }

        # Resolve follow-ups using previous context.
        effective = message
        prior_user = [m.get("content", "") for m in history if m.get("role") == "user"]
        prior_assistant = [m for m in history if m.get("role") == "assistant"]
        last_assistant_result = prior_assistant[-1] if prior_assistant else None

        # Import context resolver for database follow-up handling
        from backend.context_resolver import is_follow_up, resolve_database_followup

        if is_follow_up(message) and len(prior_user) >= 2:
            effective = resolve_database_followup(message, history, last_assistant_result)
        elif len(message.split()) <= 6 and len(prior_user) >= 2:
            previous = prior_user[-2]
            if any(token in message.lower() for token in ("what about", "how about", "and ", "same for")):
                effective = f"{previous} ; follow-up: {message}"

        schema = self._get_or_discover_schema(connection)
        plan = QueryPlanner.build_plan(effective, schema=schema, available_tables=schema.table_names())
        executor = SafeSQLExecutor(connection, schema)
        execution = executor.execute(plan)
        safe_result = self._sanitize({"rows": execution.get("rows", []), "sql": execution.get("sql")})

        # Build prior context for follow-up answers
        prior_context = None
        if is_follow_up(message) and last_assistant_result:
            prior_answer = last_assistant_result.get("content", "")
            if prior_answer and len(prior_answer) > 10:
                # Extract just the key fact from the prior answer (first sentence)
                first_sentence = prior_answer.split(".")[0].strip()
                if first_sentence:
                    prior_context = first_sentence

        answer = format_answer(message, plan, execution, prior_context=prior_context)

        # Optional custom LLM polish with validation already in answer_formatter path style.
        composed = self.custom_llm.compose_with_context(message, str(safe_result)[:500], answer)
        final_answer = composed.get("answer") or answer
        if "Question:" in final_answer or not final_answer.strip():
            final_answer = answer

        if plan.tool == "unsupported":
            # Fall through opportunity for knowledge if DB cannot answer.
            return {
                "answer": final_answer,
                "route": "database",
                "tool": plan.tool,
                "table": plan.table,
                "result": safe_result,
                "plan": plan.model_dump(),
                "llm": "custom-gpt",
                "llm_used": bool(composed.get("llm_used")),
                "retrieval": [],
                "unsupported": True,
            }

        return {
            "answer": final_answer,
            "route": "database",
            "tool": plan.tool,
            "table": plan.table,
            "result": safe_result,
            "plan": plan.model_dump(),
            "llm": "custom-gpt",
            "llm_used": bool(composed.get("llm_used")),
            "retrieval": [],
        }

    @staticmethod
    def _is_relevant_answer(question: str, answer: str) -> bool:
        """Check if a retrieved answer is actually relevant to the question.

        Uses word overlap as a simple relevance signal.  If the answer
        shares almost no content words with the question, it's likely
        irrelevant (e.g., trading content for a general knowledge question).
        """
        import re
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "what", "how",
            "why", "who", "when", "where", "which", "do", "does", "did",
            "have", "has", "had", "can", "could", "should", "would",
            "will", "shall", "may", "of", "in", "on", "at", "to",
            "for", "with", "by", "from", "as", "about", "into",
            "it", "its", "this", "that", "me", "my", "your", "we",
            "simple", "language", "example", "explain", "tell", "about",
            "kya", "hai", "ka", "ke", "ki", "ko", "mein", "se",
            "aur", "bhi", "nahi", "ho", "ye", "wo", "samjhao", "batao",
        }
        def _words(text: str) -> set:
            return {
                w for w in re.findall(r"[a-z0-9]+", text.lower())
                if w not in stopwords and len(w) > 2
            }
        q_words = _words(question)
        a_words = _words(answer)
        if not q_words:
            return True  # Can't determine -> assume relevant.
        overlap = len(q_words & a_words)
        # At least one content word from the question should appear in the answer
        return overlap >= 1

    def _handle_knowledge(self, message: str, connection, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Always ensure knowledge index (works with or without database)
        try:
            self.ensure_knowledge_index(connection)
        except Exception as exc:
            print(f"_handle_knowledge: ensure_knowledge_index failed: {exc}")
        schema = self._get_or_discover_schema(connection)
        try:
            hits = self.knowledge_service.retrieve(message, limit=5)
        except Exception as exc:
            print(f"_handle_knowledge: retrieve failed (Qdrant may be unavailable): {exc}")
            hits = []
        draft = self.knowledge_service.answer_from_retrieval(message, hits)

        # Check if the retrieved answer is usable
        draft_bad = (
            not draft
            or len(draft.strip()) < 8
            or "User:" in draft
            or "Assistant:" in draft
            or not self._is_relevant_answer(message, draft)
        )
        if draft_bad:
            general = self.custom_llm.answer_general(message, context=self._history_context(history))
            return {
                "answer": general["answer"],
                "route": "general",
                "tool": "custom_llm",
                "table": None,
                "result": {"hits": 0, "fallback": True},
                "plan": {"tool": "custom_llm", "intent": "general"},
                "llm": "custom-gpt",
                "llm_used": bool(general.get("llm_used")),
                "retrieval": [],
            }

        composed = self.custom_llm.compose_with_context(message, draft[:800], draft)
        answer = composed.get("answer") or draft
        if "Question:" in answer or "User:" in answer or len(answer.strip()) < 8:
            answer = draft
        return {
            "answer": answer,
            "route": "knowledge",
            "tool": "qdrant_retrieval",
            "table": None,
            "result": {
                "hits": [
                    {
                        "title": h.get("title"),
                        "source": h.get("source"),
                        "score": h.get("score"),
                        "text": h.get("text"),
                        "metadata": h.get("metadata"),
                    }
                    for h in hits
                ]
            },
            "plan": {"tool": "qdrant_retrieval", "intent": "knowledge", "top_k": len(hits)},
            "llm": "custom-gpt",
            "llm_used": bool(composed.get("llm_used")),
            "retrieval": hits,
        }

    def _build_web_search_query(
        self, message: str, history: List[Dict[str, Any]]
    ) -> str:
        """Build a search query using smart context resolution.

        Delegates to context_resolver which handles:
        - Independent questions → search only the current message
        - Follow-up questions → resolve pronouns and produce standalone query
        - Topic-change detection → prevent context contamination
        """
        return build_web_search_query(message, history)

    def _handle_web(self, message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Handle questions requiring live web information."""
        search_query = self._build_web_search_query(message, history)
        search_response = self.web_search.search(search_query, max_results=5)

        if not search_response.ok:
            return {
                "answer": search_response.error or (
                    "I couldn't retrieve current web information right now. "
                    "Please try again later."
                ),
                "route": "web",
                "tool": "web_search",
                "table": None,
                "result": {"error": search_response.error},
                "plan": {"tool": "web_search", "intent": "web"},
                "llm": "custom-gpt",
                "llm_used": False,
                "retrieval": [],
                "sources": [],
            }

        # Build a clean grounded answer from snippets.
        category = extract_search_category(message)
        answer = self.web_search.build_answer(search_response, category=category, question=message)

        sources = [
            {"title": r.title, "url": r.url, "source": r.title}
            for r in search_response.results[:3]
        ]

        return {
            "answer": answer,
            "route": "web",
            "tool": "web_search",
            "table": None,
            "result": {
                "query": search_response.query,
                "result_count": len(search_response.results),
            },
            "plan": {"tool": "web_search", "intent": "web"},
            "llm": "custom-gpt",
            "llm_used": False,
            "retrieval": [],
            "sources": sources,
        }

    def handle(
        self,
        message: str,
        connection,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        history = history or []
        history_texts = [m.get("content", "") for m in history if m.get("role") == "user"]
        route = ConversationRouter.route(message, history_texts=history_texts)

        if route == "memory":
            return self._handle_memory(history)
        if route == "web":
            return self._handle_web(message, history)
        if route == "general":
            # For general questions, first try curated answers (fastest),
            # then try knowledge retrieval, then fall back to custom LLM.
            # This gives the best answers for questions covered in training data.
            try:
                self.ensure_knowledge_index(connection)
            except Exception as exc:
                print(f"handle: ensure_knowledge_index failed: {exc}")
            general = self._handle_general(message, history)
            # If general handler got a curated answer (not fallback), use it
            if not general.get("result", {}).get("fallback"):
                return general
            # If fallback, try knowledge retrieval for better answer
            try:
                knowledge = self._handle_knowledge(message, connection, history)
            except Exception as exc:
                print(f"handle: knowledge fallback failed: {exc}")
                return general
            # Use knowledge answer if it found something relevant
            if knowledge.get("result", {}).get("hits") and knowledge["answer"]:
                knowledge["route"] = "knowledge"
                return knowledge
            return general
        if route == "database":
            if connection is None:
                # No database — route to knowledge instead
                try:
                    return self._handle_knowledge(message, connection, history)
                except Exception as exc:
                    print(f"handle: database->knowledge fallback failed: {exc}")
                    return self._handle_general(message, history)
            result = self._handle_database(message, connection, history)
            if result.get("unsupported"):
                # Fallback to knowledge when planner cannot map the question.
                try:
                    knowledge = self._handle_knowledge(message, connection, history)
                    knowledge["answer"] = (
                        f"{result['answer']} I also searched related knowledge. {knowledge['answer']}"
                    )
                    knowledge["route"] = "database+knowledge"
                    return knowledge
                except Exception as exc:
                    print(f"handle: database+knowledge fallback failed: {exc}")
            return result

        # knowledge (default)
        # Try curated answers first (much better than Qdrant for covered topics)
        curated = self.custom_llm.curated_answers.find(message)
        if curated:
            # Check for follow-up context
            prior_user = [m.get("content", "") for m in history if m.get("role") == "user"]
            previous_message = prior_user[-2] if len(prior_user) >= 2 else None
            if previous_message and not self.custom_llm.curated_answers.find(previous_message):
                for candidate in reversed(prior_user[:-1]):
                    if self.custom_llm.curated_answers.find(candidate):
                        previous_message = candidate
                        break
            if self.custom_llm._is_follow_up(message) and previous_message:
                continued = self.custom_llm.curated_answers.continuation_for(previous_message)
                if continued:
                    return {
                        "answer": continued.answer,
                        "route": "knowledge",
                        "tool": "curated",
                        "table": None,
                        "result": {"source": continued.source},
                        "plan": {"tool": "curated", "intent": "knowledge"},
                        "llm": "custom-gpt",
                        "llm_used": False,
                        "retrieval": [],
                    }
            return {
                "answer": curated.answer,
                "route": "knowledge",
                "tool": "curated",
                "table": None,
                "result": {"source": curated.source},
                "plan": {"tool": "curated", "intent": "knowledge"},
                "llm": "custom-gpt",
                "llm_used": False,
                "retrieval": [],
            }
        # No curated answer — fall back to Qdrant retrieval
        try:
            return self._handle_knowledge(message, connection, history)
        except Exception as exc:
            print(f"handle: knowledge fallback failed: {exc}")
            return self._handle_general(message, history)
