from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.chat_history import ChatHistoryStore
from backend.orchestrator import ChatOrchestrator
from database.adapter import get_adapter, list_supported_adapters
from database.connector import DatabaseConnector
from database.schema import SchemaInspector
from database.tools import DatabaseToolRegistry


class QueryCountRequest(BaseModel):
    table: str = Field(..., min_length=1)
    where: Optional[Dict[str, Any]] = None


class QueryFindRequest(BaseModel):
    table: str = Field(..., min_length=1)
    columns: Optional[List[str]] = None
    where: Optional[Dict[str, Any]] = None
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class QueryAggregateRequest(BaseModel):
    table: str = Field(..., min_length=1)
    operation: str
    column: Optional[str] = None
    group_by: Optional[List[str]] = None
    where: Optional[Dict[str, Any]] = None


app = FastAPI(title="My Basic LLM Database Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectRequest(BaseModel):
    database_url: str = Field(..., min_length=10)


class TrainRequest(BaseModel):
    enabled: bool = False
    notes: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None


connector = DatabaseConnector()
history_store = ChatHistoryStore()
orchestrator = ChatOrchestrator()


def _ensure_answer(answer: Optional[str], fallback: str) -> str:
    text = (answer or "").strip()
    return text if text else fallback


@app.get("/model-status")
def model_status() -> Dict[str, Any]:
    status = connector.get_connection_status()
    # Never expose credentials / full URL.
    safe_db = {
        "connected": status.get("connected"),
        "database_type": status.get("database_type"),
        "database_name": status.get("database_name"),
        "host": status.get("host"),
        "url_present": status.get("url_present"),
    }
    return {
        "status": "ready",
        "llm": "custom-gpt",
        "database": safe_db,
        "adapters": list_supported_adapters(),
        "embedding": orchestrator.embedding_service.status(),
        "qdrant": orchestrator.knowledge_service.store.status(),
        "custom_llm_ready": orchestrator.custom_llm.ready,
    }


@app.post("/connect-database")
def connect_database(payload: ConnectRequest) -> Dict[str, Any]:
    try:
        connector.database_url = payload.database_url
        connector.validate_url(payload.database_url)
        connector.connect()
        return {
            "status": "connected",
            "database_type": "postgresql",
            "database_name": connector.database_name,
        }
    except Exception as exc:  # pragma: no cover - defensive backend validation
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}") from exc


@app.get("/schema")
def get_schema() -> Dict[str, Any]:
    database = connector.get_database()
    if database is None:
        raise HTTPException(status_code=400, detail="No database is connected.")
    inspector = SchemaInspector(database)
    result = inspector.get_safe_schema_summary()
    return {
        "connected": result["connected"],
        "database": result["database"],
        "schemas": [
            {
                "name": item["name"],
                "tables": [
                    {"name": table["name"], "columns": table["columns"]}
                    for table in item["tables"]
                ],
            }
            for item in result["schemas"]
        ],
    }


@app.post("/schema/refresh")
def refresh_schema() -> Dict[str, Any]:
    """Force re-discovery of the database schema (clears cache)."""
    database = connector.get_database()
    if database is None:
        raise HTTPException(status_code=400, detail="No database is connected.")
    # Invalidate orchestrator's cached schema
    orchestrator.invalidate_schema_cache()
    # Force fresh discovery
    from backend.schema_catalog import load_schema_catalog_no_cache
    schema = load_schema_catalog_no_cache(database)
    return {
        "status": "refreshed",
        "database": schema.database_name,
        "tables": len(schema.tables),
        "columns": sum(len(t.columns) for t in schema.tables.values()),
        "foreign_keys": len(schema.foreign_keys),
    }


@app.get("/adapters")
def get_adapters() -> Dict[str, Any]:
    """List all supported database adapters and their status."""
    return {"adapters": list_supported_adapters()}


@app.post("/query/count")
def query_count(payload: QueryCountRequest) -> Dict[str, Any]:
    if connector.get_database() is None:
        raise HTTPException(status_code=400, detail="No database is connected.")
    tools = DatabaseToolRegistry(connector.get_database(), allowed_tables={payload.table})
    count = tools.count_records(payload.table, where=payload.where)
    return {"table": payload.table, "count": count}


@app.post("/query/find")
def query_find(payload: QueryFindRequest) -> Dict[str, Any]:
    if connector.get_database() is None:
        raise HTTPException(status_code=400, detail="No database is connected.")
    tools = DatabaseToolRegistry(connector.get_database(), allowed_tables={payload.table})
    rows = tools.find_records(
        payload.table,
        columns=payload.columns,
        where=payload.where,
        limit=payload.limit,
        offset=payload.offset,
    )
    return {"table": payload.table, "rows": rows}


@app.post("/query/aggregate")
def query_aggregate(payload: QueryAggregateRequest) -> Dict[str, Any]:
    if connector.get_database() is None:
        raise HTTPException(status_code=400, detail="No database is connected.")
    tools = DatabaseToolRegistry(connector.get_database(), allowed_tables={payload.table})
    result = tools.aggregate_data(
        payload.table,
        operation=payload.operation,
        column=payload.column,
        group_by=payload.group_by,
        where=payload.where,
    )
    return {"table": payload.table, "result": result}


@app.get("/chat/history")
def chat_history(conversation_id: str = Query(..., min_length=8)) -> Dict[str, Any]:
    messages = history_store.get_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@app.get("/chat/conversations")
def chat_conversations(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return {"conversations": history_store.list_conversations(limit=limit)}


@app.post("/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    conversation_id = history_store.ensure_conversation(payload.conversation_id)
    timestamp = datetime.now().strftime("%I:%M %p")

    history_store.add_message(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
        timestamp=timestamp,
    )
    history = history_store.get_messages(conversation_id)

    fallback = "I could not find enough information to answer that yet."
    try:
        database = connector.ensure_healthy_connection()
        if database is None:
            # General/memory paths can still work without DB.
            result = orchestrator.handle(payload.message, connection=None, history=history)
            answer = _ensure_answer(result.get("answer"), fallback)
            history_store.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                tool=result.get("tool"),
                table_name=result.get("table"),
                plan=result.get("plan"),
                result=result.get("result"),
                timestamp=timestamp,
            )
            return {
                "answer": answer,
                "tool": result.get("tool"),
                "table": result.get("table"),
                "result": result.get("result") or {},
                "plan": result.get("plan"),
                "route": result.get("route"),
                "conversation_id": conversation_id,
                "llm": "custom-gpt",
                "llm_used": bool(result.get("llm_used")),
                "sources": result.get("sources") or [],
            }

        # Ensure knowledge index exists for semantic questions.
        orchestrator.ensure_knowledge_index(database)
        result = orchestrator.handle(payload.message, connection=database, history=history)
        answer = _ensure_answer(result.get("answer"), fallback)

        response = {
            "answer": answer,
            "tool": result.get("tool"),
            "table": result.get("table"),
            "result": result.get("result") or {},
            "plan": result.get("plan"),
            "route": result.get("route"),
            "conversation_id": conversation_id,
            "llm": "custom-gpt",
            "llm_used": bool(result.get("llm_used")),
            "sources": result.get("sources") or [],
        }
        history_store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            tool=result.get("tool"),
            table_name=result.get("table"),
            plan=result.get("plan"),
            result=result.get("result"),
            timestamp=timestamp,
        )
        return response
    except Exception as exc:
        print(f"/chat failed: {type(exc).__name__}: {exc}")
        # Provide a user-friendly error message instead of exposing internal details
        error_msg = str(exc).lower()
        if "errno 10054" in error_msg or "forcibly closed" in error_msg:
            friendly = "I'm having trouble connecting to the knowledge base right now. Please try again in a moment."
        elif "qdrant" in error_msg or "connection refused" in error_msg:
            friendly = "The knowledge service is temporarily unavailable. I can still help with general questions!"
        else:
            friendly = f"I encountered an issue processing that request. Please try again."
        answer = _ensure_answer(friendly, fallback)
        history_store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            timestamp=timestamp,
        )
        return {
            "answer": answer,
            "tool": None,
            "table": None,
            "result": {},
            "plan": None,
            "route": "error",
            "conversation_id": conversation_id,
            "llm": "custom-gpt",
        }


@app.post("/train")
def train_model(payload: TrainRequest) -> Dict[str, Any]:
    if not payload.enabled:
        return {"status": "not_started", "message": "Database-specific training is off by default."}
    return {"status": "queued", "message": "Manual training pipeline would start here."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
