from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.answer_formatter import format_answer
from backend.custom_llm import CustomLLMService
from backend.embedding_service import EmbeddingService
from backend.knowledge import KnowledgeService
from backend.query_planner import QueryPlanner
from backend.router import ConversationRouter
from backend.safe_sql import SafeSQLExecutor
from backend.schema_catalog import load_schema_catalog


class ChatOrchestrator:
    """Routes chat turns through Custom LLM, PostgreSQL, or Qdrant retrieval."""

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.knowledge_service = KnowledgeService(self.embedding_service)
        self.custom_llm = CustomLLMService()
        self._knowledge_ready = False

    def ensure_knowledge_index(self, connection) -> Dict[str, Any]:
        if self._knowledge_ready and self.knowledge_service.store.count() > 0:
            return {"ready": True, "points": self.knowledge_service.store.count()}
        # Force rebuild once per process start so stale/training vectors are replaced.
        result = self.knowledge_service.index_database(connection, force=True)
        self._knowledge_ready = bool(result.get("points", 0) > 0)
        return result

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
            answer = f"Previously, you asked: \"{last}\""
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
        previous_message = prior_user[-2] if len(prior_user) >= 2 else None
        if previous_message and not self.custom_llm.curated_answers.find(previous_message):
            for candidate in reversed(prior_user[:-1]):
                if self.custom_llm.curated_answers.find(candidate):
                    previous_message = candidate
                    break
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

        # Resolve short follow-ups using previous user question.
        effective = message
        prior_user = [m.get("content", "") for m in history if m.get("role") == "user"]
        if len(message.split()) <= 6 and len(prior_user) >= 2:
            previous = prior_user[-2]
            if any(token in message.lower() for token in ("what about", "how about", "and ", "same for")):
                effective = f"{previous} ; follow-up: {message}"

        catalog = load_schema_catalog(connection)
        plan = QueryPlanner.build_plan(effective, catalog=catalog, available_tables=catalog.table_names())
        executor = SafeSQLExecutor(connection, catalog)
        execution = executor.execute(plan)
        safe_result = self._sanitize({"rows": execution.get("rows", []), "sql": execution.get("sql")})
        answer = format_answer(message, plan, execution)

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

    def _handle_knowledge(self, message: str, connection, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if connection is not None:
            self.ensure_knowledge_index(connection)
        hits = self.knowledge_service.retrieve(message, limit=5)
        draft = self.knowledge_service.answer_from_retrieval(message, hits)
        if not draft:
            general = self.custom_llm.answer_general(message, context=self._history_context(history))
            return {
                "answer": (
                    "I could not find enough relevant knowledge for that question. "
                    + general["answer"]
                ),
                "route": "knowledge",
                "tool": "qdrant_retrieval",
                "table": None,
                "result": {"hits": 0},
                "plan": {"tool": "qdrant_retrieval", "intent": "knowledge"},
                "llm": "custom-gpt",
                "llm_used": bool(general.get("llm_used")),
                "retrieval": [],
            }

        composed = self.custom_llm.compose_with_context(message, draft[:800], draft)
        answer = composed.get("answer") or draft
        if "Question:" in answer or len(answer.strip()) < 8:
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
        if route == "general":
            return self._handle_general(message, history)
        if route == "database":
            result = self._handle_database(message, connection, history)
            if result.get("unsupported"):
                # Fallback to knowledge when planner cannot map the question.
                knowledge = self._handle_knowledge(message, connection, history)
                knowledge["answer"] = (
                    f"{result['answer']} I also searched related knowledge. {knowledge['answer']}"
                )
                knowledge["route"] = "database+knowledge"
                return knowledge
            return result

        # knowledge (default)
        return self._handle_knowledge(message, connection, history)
