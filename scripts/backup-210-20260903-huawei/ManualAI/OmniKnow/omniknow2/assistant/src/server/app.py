import asyncio
import base64
import json
import logging
import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, List, Optional, cast
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from pydantic import BaseModel
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from src.config.configuration import get_recursion_limit
from src.config.loader import get_bool_env, get_str_env
from src.config.report_style import ReportStyle
from src.config.tools import SELECTED_RAG_PROVIDER
from src.neo.checkpoint import chat_stream_message
from src.neo.utils import (
    build_clarified_topic_from_history,
    reconstruct_clarification_history,
)
from src.llms.llm import (
    get_configured_llm_models,
    reset_runtime_llm_type,
    set_runtime_llm_type,
)
from src.neo.builder import build_graph_with_memory as build_neo_graph_with_memory
from src.neo.kg import generate_knowledge_graph
from src.neo.title_summary import generate_title_summary
from src.report_generator.builder import build_graph_with_memory as build_graph_reporter_with_memory
from src.quest.schemas import (
    QuestChatRequest,
    QuestEvaluationRecord,
    QuestGenerateRequest,
    QuestGenerateResponse,
    QuestScoreRequest,
    QuestScoreResponse,
)
from src.quest.service import QuestService
from src.subagents.rag.builder import build_retriever
from src.subagents.rag.retriever import Resource
from src.server.chat_request import (
    ChatRequest,
    NeoChatRequest,
    NeoTitleSummaryRequest,
    TTSRequest,
)
from src.server.config_request import ConfigResponse
from src.server.mcp_request import MCPServerMetadataRequest, MCPServerMetadataResponse
from src.server.mcp_utils import load_mcp_tools
from src.server.rag_request import (
    RAGConfigResponse,
    RAGResourceRequest,
    RAGResourcesResponse,
)
from src.tools import VolcengineTTS
from src.utils.json_utils import sanitize_args
from src.utils.log_sanitizer import (
    sanitize_agent_name,
    sanitize_log_input,
    sanitize_thread_id,
    sanitize_tool_name,
    sanitize_user_content,
)

logger = logging.getLogger(__name__)

# Configure Windows event loop policy for PostgreSQL compatibility
# On Windows, psycopg requires a selector-based event loop, not the default ProactorEventLoop
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"

app = FastAPI(
    title="Omniknow API",
    description="API for Omni",
    version="0.1.0",
)

# Add CORS middleware
# It's recommended to load the allowed origins from an environment variable
# for better security and flexibility across different environments.
def _expand_loopback_origins(origins: list[str]) -> list[str]:
    """Treat localhost and 127.0.0.1 as equivalent for local development."""
    expanded: list[str] = []
    seen: set[str] = set()

    for origin in origins:
        origin = origin.strip()
        if not origin or origin in seen:
            continue

        expanded.append(origin)
        seen.add(origin)

        parsed = urlparse(origin)
        hostname = parsed.hostname
        if hostname not in {"localhost", "127.0.0.1"}:
            continue

        alias_host = "127.0.0.1" if hostname == "localhost" else "localhost"
        netloc = alias_host
        if parsed.port is not None:
            netloc = f"{alias_host}:{parsed.port}"

        alias_origin = parsed._replace(netloc=netloc).geturl()
        if alias_origin not in seen:
            expanded.append(alias_origin)
            seen.add(alias_origin)

    return expanded


allowed_origins_str = get_str_env("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = _expand_loopback_origins(allowed_origins_str.split(","))

logger.info(f"Allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict to specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Use the configured list of methods
    allow_headers=["*"],  # Now allow all headers, but can be restricted further
)
in_memory_store = InMemoryStore()
graph_neo = build_neo_graph_with_memory()
graph_reporter = build_graph_reporter_with_memory()

TABLE_PREVIEW_DB_URL = get_str_env(
    "TABLE_PREVIEW_DB_URL",
    "mysql+pymysql://root:cc123456@127.0.0.1:19806/tesla_service?charset=utf8mb4",
)
KG_JSON_ROOT = Path(__file__).resolve().parents[2] / "kg_json"


class TableDetailReq(BaseModel):
    table_name: str
    limit: int = 100


class NeoKGGenerateRequest(BaseModel):
    resource: Resource
    use_llm: bool = True


@lru_cache(maxsize=1)
def get_quest_service() -> QuestService:
    return QuestService()


@lru_cache(maxsize=1)
def _get_table_preview_engine() -> Engine:
    return create_engine(
        TABLE_PREVIEW_DB_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def _get_preview_table_names() -> list[str]:
    return inspect(_get_table_preview_engine()).get_table_names()


def _safe_collection_dir_name(collection_name: str) -> str:
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", collection_name.strip())
    return safe_name.strip("._") or "collection"


def _save_knowledge_graph_json(
    collection_name: str,
    graph_json: dict[str, Any],
) -> Path:
    localtime = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = KG_JSON_ROOT / _safe_collection_dir_name(collection_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"kg_{localtime}.json"
    output_path.write_text(
        json.dumps(graph_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


@app.post("/table/name")
def list_tables() -> dict[str, Any]:
    try:
        return {"tables": _get_preview_table_names()}
    except Exception:
        logger.exception("Failed to list preview tables.")
        raise HTTPException(
            status_code=500,
            detail=INTERNAL_SERVER_ERROR_DETAIL,
        )


@app.post("/table/detail")
def table_head(req: TableDetailReq) -> dict[str, Any]:
    table_name = req.table_name.strip()
    limit = req.limit

    if not table_name:
        raise HTTPException(status_code=400, detail="table_name cannot be empty")

    try:
        if table_name not in _get_preview_table_names():
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        sql = text(f"SELECT * FROM `{table_name}` LIMIT :limit")
        with _get_table_preview_engine().connect() as conn:
            result = conn.execute(sql, {"limit": limit})
            rows = result.mappings().all()
            data = [dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to load preview rows for table '%s'.", table_name)
        raise HTTPException(
            status_code=500,
            detail=INTERNAL_SERVER_ERROR_DETAIL,
        )

    return {"table": table_name, "limit": limit, "count": len(data), "rows": data}


@app.post("/api/quest/generate", response_model=QuestGenerateResponse)
async def generate_questions(request: QuestGenerateRequest):
    try:
        service = get_quest_service()
        return await asyncio.to_thread(service.generate_questions, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to generate quest questions: %s", exc)
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL) from exc


@app.post("/api/quest/chat/stream")
async def chat_with_quest_kb_stream(request: QuestChatRequest):
    return StreamingResponse(
        _astream_quest_chat_generator(request),
        media_type="text/event-stream",
    )


@app.post("/api/quest/score", response_model=QuestScoreResponse)
async def score_quest_answer(request: QuestScoreRequest):
    try:
        service = get_quest_service()
        return await asyncio.to_thread(service.score_answer, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to score quest answer: %s", exc)
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL) from exc


@app.post("/api/quest/evaluate", response_class=PlainTextResponse)
async def evaluate_quest_exam(request: list[QuestEvaluationRecord]):
    try:
        service = get_quest_service()
        return await asyncio.to_thread(service.evaluate_exam, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate quest exam: %s", exc)
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL) from exc


@app.post("/api/neo/chat/stream")
async def neo_chat_stream(request: NeoChatRequest):
    return await _stream_chat_via_neo(request)


@app.post("/api/neo/title/summary")
async def neo_title_summary(request: NeoTitleSummaryRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    token = set_runtime_llm_type(request.llm_type)
    try:
        title = generate_title_summary(
            [message.model_dump() for message in request.messages],
            request.locale or "zh-CN",
        )
    finally:
        reset_runtime_llm_type(token)
    return {"title": title}


@app.post("/api/neo/kg/generate")
async def neo_generate_knowledge_graph(request: NeoKGGenerateRequest):
    collection_name = request.resource.uri.strip()
    if not collection_name:
        raise HTTPException(status_code=400, detail="resource.uri cannot be empty")

    try:
        graph_json = await asyncio.to_thread(
            generate_knowledge_graph,
            resource=request.resource,
            use_llm=request.use_llm,
        )
        output_path = await asyncio.to_thread(
            _save_knowledge_graph_json,
            collection_name,
            graph_json,
        )
        return {
            "resource": request.resource.model_dump(),
            "path": str(output_path),
            "graph": graph_json,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to generate knowledge graph for collection '%s': %s",
            collection_name,
            exc,
        )
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL) from exc


@app.post("/api/reporter/stream")
async def reporter_stream(request: ChatRequest):
    logger.debug(f"get the request locale : {request.locale}")

    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())

    return StreamingResponse(
        _astream_workflow_generator_reporter(
            request.model_dump()["messages"],
            thread_id,
            request.resources,
            request.max_plan_iterations,
            request.max_step_num,
            request.max_search_results,
            request.auto_accepted_plan,
            request.interrupt_feedback,
            request.mcp_settings or {},
            request.enable_background_investigation,
            request.report_style,
            request.enable_deep_thinking,
            request.enable_clarification,
            request.max_clarification_rounds,
            request.locale,
            request.interrupt_before_tools,
            request.image_url,
            request.user_id,
            request.enable_longterm_memory,
            request.llm_type,
        ),
        media_type="text/event-stream",
    )


def _resolve_thread_id(thread_id: str | None) -> str:
    if not thread_id or thread_id == "__default__":
        return str(uuid4())
    return thread_id


async def _stream_chat_via_neo(request: NeoChatRequest) -> StreamingResponse:
    logger.debug("get the neo request locale : %s", request.locale)

    thread_id = _resolve_thread_id(request.thread_id)
    return StreamingResponse(
        _astream_neo_workflow_generator(
            request.model_dump()["messages"],
            thread_id,
            request.resources,
            request.mcp_settings or {},
            request.locale,
            request.image_url,
            request.user_id,
            request.enable_longterm_memory,
            request.llm_type,
        ),
        media_type="text/event-stream",
    )


def _validate_tool_call_chunks(tool_call_chunks):
    """Validate and log tool call chunk structure for debugging."""
    if not tool_call_chunks:
        return
    
    logger.debug(f"Validating tool_call_chunks: count={len(tool_call_chunks)}")
    
    indices_seen = set()
    tool_ids_seen = set()
    
    for i, chunk in enumerate(tool_call_chunks):
        index = chunk.get("index")
        tool_id = chunk.get("id")
        name = chunk.get("name", "")
        has_args = "args" in chunk
        
        logger.debug(
            f"Chunk {i}: index={index}, id={tool_id}, name={name}, "
            f"has_args={has_args}, type={chunk.get('type')}"
        )
        
        if index is not None:
            indices_seen.add(index)
        if tool_id:
            tool_ids_seen.add(tool_id)
    
    if len(indices_seen) > 1:
        logger.debug(
            f"Multiple indices detected: {sorted(indices_seen)} - "
            f"This may indicate consecutive tool calls"
        )


def _process_tool_call_chunks(tool_call_chunks):
    """
    Process tool call chunks with proper index-based grouping.
    
    This function handles the concatenation of tool call chunks that belong
    to the same tool call (same index) while properly segregating chunks
    from different tool calls (different indices).
    
    The issue: In streaming, LangChain's ToolCallChunk concatenates string
    attributes (name, args) when chunks have the same index. We need to:
    1. Group chunks by index
    2. Detect index collisions with different tool names
    3. Accumulate arguments for the same index
    4. Return properly segregated tool calls
    """
    if not tool_call_chunks:
        return []
    
    _validate_tool_call_chunks(tool_call_chunks)
    
    chunks = []
    chunk_by_index = {}  # Group chunks by index to handle streaming accumulation
    
    for chunk in tool_call_chunks:
        index = chunk.get("index")
        chunk_id = chunk.get("id")
        
        if index is not None:
            # Create or update entry for this index
            if index not in chunk_by_index:
                chunk_by_index[index] = {
                    "name": "",
                    "args": "",
                    "id": chunk_id or "",
                    "index": index,
                    "type": chunk.get("type", ""),
                }
            
            # Validate and accumulate tool name
            chunk_name = chunk.get("name", "")
            if chunk_name:
                stored_name = chunk_by_index[index]["name"]
                
                # Check for index collision with different tool names
                if stored_name and stored_name != chunk_name:
                    logger.warning(
                        f"Tool name mismatch detected at index {index}: "
                        f"'{stored_name}' != '{chunk_name}'. "
                        f"This may indicate a streaming artifact or consecutive tool calls "
                        f"with the same index assignment."
                    )
                    # Keep the first name to prevent concatenation
                else:
                    chunk_by_index[index]["name"] = chunk_name
            
            # Update ID if new one provided
            if chunk_id and not chunk_by_index[index]["id"]:
                chunk_by_index[index]["id"] = chunk_id
            
            # Accumulate arguments
            if chunk.get("args"):
                chunk_by_index[index]["args"] += chunk.get("args", "")
        else:
            # Handle chunks without explicit index (edge case)
            logger.debug(f"Chunk without index encountered: {chunk}")
            chunks.append({
                "name": chunk.get("name", ""),
                "args": sanitize_args(chunk.get("args", "")),
                "id": chunk.get("id", ""),
                "index": 0,
                "type": chunk.get("type", ""),
            })
    
    # Convert indexed chunks to list, sorted by index for proper order
    for index in sorted(chunk_by_index.keys()):
        chunk_data = chunk_by_index[index]
        chunk_data["args"] = sanitize_args(chunk_data["args"])
        chunks.append(chunk_data)
        logger.debug(
            f"Processed tool call: index={index}, name={chunk_data['name']}, "
            f"id={chunk_data['id']}"
        )
    
    return chunks


def _get_agent_name(agent, message_metadata):
    """Extract agent name from agent tuple."""
    metadata_agent_name = message_metadata.get("agent_name", "")
    if metadata_agent_name:
        return metadata_agent_name

    if isinstance(agent, str) and agent:
        return agent.split(":")[0] if ":" in agent else agent

    if isinstance(agent, (list, tuple)):
        for item in reversed(agent):
            if isinstance(item, str) and item:
                return item.split(":")[0] if ":" in item else item

    return message_metadata.get("langgraph_node", "unknown")


def _create_event_stream_message(
    message_chunk, message_metadata, thread_id, agent_name
):
    """Create base event stream message."""
    content = message_chunk.content
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)

    event_stream_message = {
        "thread_id": thread_id,
        "agent": agent_name,
        "id": message_chunk.id,
        "role": "assistant",
        "checkpoint_ns": message_metadata.get("checkpoint_ns", ""),
        "langgraph_node": message_metadata.get("langgraph_node", ""),
        "langgraph_path": message_metadata.get("langgraph_path", ""),
        "langgraph_step": message_metadata.get("langgraph_step", ""),
        "step_id": message_metadata.get("step_id", ""),
        "content": content,
    }

    # Add optional fields
    if message_chunk.additional_kwargs.get("reasoning_content"):
        event_stream_message["reasoning_content"] = message_chunk.additional_kwargs[
            "reasoning_content"
        ]

    if message_chunk.response_metadata.get("finish_reason"):
        event_stream_message["finish_reason"] = message_chunk.response_metadata.get(
            "finish_reason"
        )

    return event_stream_message


def _create_interrupt_event(thread_id, event_data):
    """Create interrupt event."""
    interrupt = event_data["__interrupt__"][0]
    # Use the 'id' attribute (LangGraph 1.0+) instead of deprecated 'ns[0]'
    interrupt_id = getattr(interrupt, "id", None) or thread_id
    return _make_event(
        "interrupt",
        {
            "thread_id": thread_id,
            "id": interrupt_id,
            "role": "assistant",
            "content": interrupt.value,
            "finish_reason": "interrupt",
            "options": [
                {"text": "修改计划", "value": "edit_plan"},
                {"text": "开始任务", "value": "accepted"},
            ],
        },
    )


def _create_fact_check_review_event(thread_id, agent, event_data):
    """Create a targeted fact check review event for neo update streaming."""
    node_names = [key for key in event_data.keys() if key != "__metadata__"]
    if len(node_names) != 1:
        return None

    langgraph_node = node_names[0]
    node_update = event_data.get(langgraph_node)
    if not isinstance(node_update, dict):
        return None

    fact_check_review = node_update.get("fact_check_review")
    if not fact_check_review:
        return None

    return _make_event(
        "fact_check_review",
        {
            "thread_id": thread_id,
            "agent": _get_agent_name(agent, {}),
            "langgraph_node": langgraph_node,
            "fact_check_review": fact_check_review,
            "grounding_score": node_update.get("grounding_score", 0.0),
        },
    )


def _process_initial_messages(message, thread_id):
    """Process initial messages and yield formatted events."""
    json_data = json.dumps(
        {
            "thread_id": thread_id,
            "id": "run--" + message.get("id", uuid4().hex),
            "role": "user",
            "content": message.get("content", ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chat_stream_message(
        thread_id, f"event: message_chunk\ndata: {json_data}\n\n", "none"
    )


async def _process_message_chunk(message_chunk, message_metadata, thread_id, agent):
    """Process a single message chunk and yield appropriate events."""

    agent_name = _get_agent_name(agent, message_metadata)
    safe_agent_name = sanitize_agent_name(agent_name)
    safe_thread_id = sanitize_thread_id(thread_id)
    safe_agent = sanitize_agent_name(agent)
    logger.debug(f"[{safe_thread_id}] _process_message_chunk started for agent={safe_agent_name}")
    logger.debug(f"[{safe_thread_id}] Extracted agent_name: {safe_agent_name}")
    
    event_stream_message = _create_event_stream_message(
        message_chunk, message_metadata, thread_id, agent_name
    )

    if isinstance(message_chunk, ToolMessage):
        # Tool Message - Return the result of the tool call
        logger.debug(f"[{safe_thread_id}] Processing ToolMessage")
        tool_call_id = message_chunk.tool_call_id
        event_stream_message["tool_call_id"] = tool_call_id
        event_stream_message["tool_name"] = message_chunk.name
        
        # Validate tool_call_id for debugging
        if tool_call_id:
            safe_tool_id = sanitize_log_input(tool_call_id, max_length=100)
            logger.debug(f"[{safe_thread_id}] ToolMessage with tool_call_id: {safe_tool_id}")
        else:
            logger.warning(f"[{safe_thread_id}] ToolMessage received without tool_call_id")
        
        logger.debug(f"[{safe_thread_id}] Yielding tool_call_result event")
        yield _make_event("tool_call_result", event_stream_message)
    elif isinstance(message_chunk, AIMessageChunk):
        # AI Message - Raw message tokens
        has_tool_calls = bool(message_chunk.tool_calls)
        has_chunks = bool(message_chunk.tool_call_chunks)
        logger.debug(f"[{safe_thread_id}] Processing AIMessageChunk, tool_calls={has_tool_calls}, tool_call_chunks={has_chunks}")
        
        if message_chunk.tool_calls:
            # AI Message - Tool Call (complete tool calls)
            safe_tool_names = [sanitize_tool_name(tc.get('name', 'unknown')) for tc in message_chunk.tool_calls]
            logger.debug(f"[{safe_thread_id}] AIMessageChunk has complete tool_calls: {safe_tool_names}")
            event_stream_message["tool_calls"] = message_chunk.tool_calls
            
            # Process tool_call_chunks with proper index-based grouping
            processed_chunks = _process_tool_call_chunks(
                message_chunk.tool_call_chunks
            )
            if processed_chunks:
                event_stream_message["tool_call_chunks"] = processed_chunks
                safe_chunk_names = [sanitize_tool_name(c.get('name')) for c in processed_chunks]
                logger.debug(
                    f"[{safe_thread_id}] Tool calls: {safe_tool_names}, "
                    f"Processed chunks: {len(processed_chunks)}"
                )
            
            logger.debug(f"[{safe_thread_id}] Yielding tool_calls event")
            yield _make_event("tool_calls", event_stream_message)
        elif message_chunk.tool_call_chunks:
            # AI Message - Tool Call Chunks (streaming)
            chunks_count = len(message_chunk.tool_call_chunks)
            logger.debug(f"[{safe_thread_id}] AIMessageChunk has streaming tool_call_chunks: {chunks_count} chunks")
            processed_chunks = _process_tool_call_chunks(
                message_chunk.tool_call_chunks
            )
            
            # Emit separate events for chunks with different indices (tool call boundaries)
            if processed_chunks:
                prev_chunk = None
                for chunk in processed_chunks:
                    current_index = chunk.get("index")
                    
                    # Log index transitions to detect tool call boundaries
                    if prev_chunk is not None and current_index != prev_chunk.get("index"):
                        prev_name = sanitize_tool_name(prev_chunk.get('name'))
                        curr_name = sanitize_tool_name(chunk.get('name'))
                        logger.debug(
                            f"[{safe_thread_id}] Tool call boundary detected: "
                            f"index {prev_chunk.get('index')} ({prev_name}) -> "
                            f"{current_index} ({curr_name})"
                        )
                    
                    prev_chunk = chunk
                
                # Include all processed chunks in the event
                event_stream_message["tool_call_chunks"] = processed_chunks
                safe_chunk_names = [sanitize_tool_name(c.get('name')) for c in processed_chunks]
                logger.debug(
                    f"[{safe_thread_id}] Streamed {len(processed_chunks)} tool call chunk(s): "
                    f"{safe_chunk_names}"
                )
            
            logger.debug(f"[{safe_thread_id}] Yielding tool_call_chunks event")
            yield _make_event("tool_call_chunks", event_stream_message)
        else:
            # AI Message - Raw message tokens
            content_len = len(message_chunk.content) if isinstance(message_chunk.content, str) else 0
            logger.debug(f"[{safe_thread_id}] AIMessageChunk is raw message tokens, content_len={content_len}")
            yield _make_event("message_chunk", event_stream_message)


async def _stream_graph_events(
    graph_instance, workflow_input, workflow_config, thread_id
):
    """Stream events from the graph and process them."""
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(f"[{safe_thread_id}] Starting graph event stream with agent nodes")
    try:
        event_count = 0
        async for agent, _, event_data in graph_instance.astream(
            workflow_input,
            config=workflow_config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            event_count += 1
            safe_agent = sanitize_agent_name(agent)
            logger.debug(f"[{safe_thread_id}] Graph event #{event_count} received from agent: {safe_agent}")
            
            if isinstance(event_data, dict):
                if "__interrupt__" in event_data:
                    logger.debug(
                        f"[{safe_thread_id}] Processing interrupt event: "
                        f"id={getattr(event_data['__interrupt__'][0], 'id', 'unknown') if isinstance(event_data['__interrupt__'], (list, tuple)) and len(event_data['__interrupt__']) > 0 else 'unknown'}, "
                        f"value_len={len(getattr(event_data['__interrupt__'][0], 'value', '')) if isinstance(event_data['__interrupt__'], (list, tuple)) and len(event_data['__interrupt__']) > 0 and hasattr(event_data['__interrupt__'][0], 'value') and hasattr(event_data['__interrupt__'][0].value, '__len__') else 'unknown'}"
                    )
                    yield _create_interrupt_event(thread_id, event_data)
                    continue

                fact_check_review_event = _create_fact_check_review_event(
                    thread_id, agent, event_data
                )
                if fact_check_review_event:
                    logger.debug(f"[{safe_thread_id}] Yielding fact_check_review event")
                    yield fact_check_review_event
                else:
                    logger.debug(
                        f"[{safe_thread_id}] Dict event without interrupt or fact_check_review, skipping"
                    )
                continue

            message_chunk, message_metadata = cast(
                tuple[BaseMessage, dict[str, Any]], event_data
            )
            
            safe_node = sanitize_agent_name(message_metadata.get('langgraph_node', 'unknown'))
            safe_step = sanitize_log_input(message_metadata.get('langgraph_step', 'unknown'))
            logger.debug(
                f"[{safe_thread_id}] Processing message chunk: "
                f"type={type(message_chunk).__name__}, "
                f"node={safe_node}, "
                f"step={safe_step}"
            )

            async for event in _process_message_chunk(
                message_chunk, message_metadata, thread_id, agent
            ):
                yield event
        
        logger.debug(f"[{safe_thread_id}] Graph event stream completed. Total events: {event_count}")
        yield _make_event(
            "finish",
            {
                "thread_id": safe_thread_id,
                "info": f"[{safe_thread_id}] Graph event stream completed. Total events: {event_count}",
                "finish_reason": "finish",
            },
        )


    except asyncio.CancelledError:
        # User cancelled/interrupted the stream - this is normal, not an error
        logger.info(f"[{safe_thread_id}] Graph event stream cancelled by user after {event_count} events")
        # Re-raise to signal cancellation properly without yielding an error event
        raise
    except Exception as e:
        logger.exception(f"[{safe_thread_id}] Error during graph execution")
        yield _make_event(
            "error",
            {
                "thread_id": thread_id,
                "info": f"Error during graph execution: {e}",
                "finish_reason": "finish",
            },
        )


async def _astream_neo_workflow_generator(
    messages: List[dict],
    thread_id: str,
    resources: List[Resource],
    mcp_settings: dict,
    locale: str = "en-US",
    image_url: str = "",
    user_id: str = "anonymous",
    enable_longterm_memory: bool = False,
    llm_type: str = "basic",
):
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(
        f"[{safe_thread_id}] _astream_neo_workflow_generator starting: "
        f"messages_count={len(messages)}"
    )

    for message in messages:
        if isinstance(message, dict) and "content" in message:
            _process_initial_messages(message, thread_id)

    latest_message_content = messages[-1]["content"] if messages else ""
    workflow_input = {
        "messages": messages,
        "research_topic": latest_message_content,
        "locale": locale,
        "scheduler_thought": "",
        "resources": resources,
        "observations": [],
        "completed_steps": [],
        "current_step": None,
        "final_answer": "",
        "task_title": "",
        "preprocess_done": False,
        "preprocess_summary": "",
        "image_url": image_url,
        "user_id": user_id,
        "enable_longterm_memory": enable_longterm_memory,
    }

    configurable = {
        "thread_id": thread_id,
        "resources": resources,
        "mcp_settings": mcp_settings,
        "llm_type": llm_type,
    }
    workflow_config = {
        **configurable,
        "configurable": configurable,
        "recursion_limit": get_recursion_limit(),
    }

    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    checkpoint_url = get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "")
    connection_kwargs = {
        "autocommit": True,
        "row_factory": "dict_row",
        "prepare_threshold": 0,
    }

    runtime_llm_token = set_runtime_llm_type(llm_type)
    try:
        if checkpoint_saver and checkpoint_url != "":
            if checkpoint_url.startswith("postgresql://"):
                async with AsyncConnectionPool(
                    checkpoint_url, kwargs=connection_kwargs
                ) as conn:
                    checkpointer = AsyncPostgresSaver(conn)
                    await checkpointer.setup()
                    graph_neo.checkpointer = checkpointer
                    graph_neo.store = in_memory_store
                    async for event in _stream_graph_events(
                        graph_neo, workflow_input, workflow_config, thread_id
                    ):
                        yield event
            elif checkpoint_url.startswith("mongodb://") or checkpoint_url.startswith(
                "mongodb+srv://"
            ):
                async with AsyncMongoDBSaver.from_conn_string(checkpoint_url) as checkpointer:
                    graph_neo.checkpointer = checkpointer
                    graph_neo.store = in_memory_store
                    async for event in _stream_graph_events(
                        graph_neo, workflow_input, workflow_config, thread_id
                    ):
                        yield event
            else:
                raise ValueError("Unsupported LANGGRAPH_CHECKPOINT_DB_URL for neo graph")
        else:
            async for event in _stream_graph_events(
                graph_neo, workflow_input, workflow_config, thread_id
            ):
                yield event
    finally:
        reset_runtime_llm_type(runtime_llm_token)


async def _astream_workflow_generator_reporter(
    messages: List[dict],
    thread_id: str,
    resources: List[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: str,
    mcp_settings: dict,
    enable_background_investigation: bool,
    report_style: ReportStyle,
    enable_deep_thinking: bool,
    enable_clarification: bool,
    max_clarification_rounds: int,
    locale: str = "en-US",
    interrupt_before_tools: Optional[List[str]] = None,
    image_url: str = "",
    user_id: str = "anonymous",
    enable_longterm_memory: bool = False,
    llm_type: str = "basic",
):
    safe_thread_id = sanitize_thread_id(thread_id)
    safe_feedback = sanitize_log_input(interrupt_feedback) if interrupt_feedback else ""
    logger.debug(
        f"[{safe_thread_id}] _astream_workflow_generator starting: "
        f"messages_count={len(messages)}, "
        f"auto_accepted_plan={auto_accepted_plan}, "
        f"interrupt_feedback={safe_feedback}, "
        f"interrupt_before_tools={interrupt_before_tools}"
    )
    
    # Process initial messages
    logger.debug(f"[{safe_thread_id}] Processing {len(messages)} initial messages")
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            safe_content = sanitize_user_content(message.get('content', ''))
            logger.debug(f"[{safe_thread_id}] Sending initial message to client: {safe_content}")
            _process_initial_messages(message, thread_id)

    logger.debug(f"[{safe_thread_id}] Reconstructing clarification history")
    clarification_history = reconstruct_clarification_history(messages)

    logger.debug(f"[{safe_thread_id}] Building clarified topic from history")
    clarified_topic, clarification_history = build_clarified_topic_from_history(
        clarification_history
    )
    latest_message_content = messages[-1]["content"] if messages else ""
    clarified_research_topic = clarified_topic or latest_message_content
    safe_topic = sanitize_user_content(clarified_research_topic)
    logger.debug(f"[{safe_thread_id}] Clarified research topic: {safe_topic}")

    # Prepare workflow input
    logger.debug(f"[{safe_thread_id}] Preparing workflow input")
    workflow_input = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
        "research_topic": latest_message_content,
        "clarification_history": clarification_history,
        "clarified_research_topic": clarified_research_topic,
        "enable_clarification": enable_clarification,
        "max_clarification_rounds": max_clarification_rounds,
        "locale": locale,
        "image_url": image_url,
        "user_id": user_id,
        "enable_longterm_memory": enable_longterm_memory
    }

    if not auto_accepted_plan and interrupt_feedback:
        logger.debug(f"[{safe_thread_id}] Creating resume command with interrupt_feedback: {safe_feedback}")
        resume_msg = f"[{interrupt_feedback}]"
        if messages:
            resume_msg += f" {messages[-1]['content']}"
        workflow_input = Command(resume=resume_msg)

    # Prepare workflow config
    logger.debug(
        f"[{safe_thread_id}] Preparing workflow config: "
        f"max_plan_iterations={max_plan_iterations}, "
        f"max_step_num={max_step_num}, "
        f"report_style={report_style.value}, "
        f"enable_deep_thinking={enable_deep_thinking}"
    )
    configurable = {
        "thread_id": thread_id,
        "resources": resources,
        "max_plan_iterations": max_plan_iterations,
        "max_step_num": max_step_num,
        "max_search_results": max_search_results,
        "mcp_settings": mcp_settings,
        "report_style": report_style.value,
        "enable_deep_thinking": enable_deep_thinking,
        "interrupt_before_tools": interrupt_before_tools,
        "llm_type": llm_type,
    }
    workflow_config = {
        **configurable,
        "configurable": configurable,
        "recursion_limit": get_recursion_limit(),
    }

    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    checkpoint_url = get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "")
    
    logger.debug(
        f"[{safe_thread_id}] Checkpoint configuration: "
        f"saver_enabled={checkpoint_saver}, "
        f"url_configured={bool(checkpoint_url)}"
    )
    
    # Handle checkpointer if configured
    connection_kwargs = {
        "autocommit": True,
        "row_factory": "dict_row",
        "prepare_threshold": 0,
    }
    runtime_llm_token = set_runtime_llm_type(llm_type)
    try:
        if checkpoint_saver and checkpoint_url != "":
            if checkpoint_url.startswith("postgresql://"):
                logger.info(f"[{safe_thread_id}] Starting async postgres checkpointer")
                logger.debug(f"[{safe_thread_id}] Setting up PostgreSQL connection pool")
                async with AsyncConnectionPool(
                    checkpoint_url, kwargs=connection_kwargs
                ) as conn:
                    logger.debug(f"[{safe_thread_id}] Initializing AsyncPostgresSaver")
                    checkpointer = AsyncPostgresSaver(conn)
                    await checkpointer.setup()
                    logger.debug(f"[{safe_thread_id}] Attaching checkpointer to graph")
                    graph_reporter.checkpointer = checkpointer
                    graph_reporter.store = in_memory_store
                    logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
                    async for event in _stream_graph_events(
                        graph_reporter, workflow_input, workflow_config, thread_id
                    ):
                        yield event
                    logger.debug(f"[{safe_thread_id}] Graph event streaming completed")

            if checkpoint_url.startswith("mongodb://"):
                logger.info(f"[{safe_thread_id}] Starting async mongodb checkpointer")
                logger.debug(f"[{safe_thread_id}] Setting up MongoDB connection")
                async with AsyncMongoDBSaver.from_conn_string(
                    checkpoint_url
                ) as checkpointer:
                    logger.debug(f"[{safe_thread_id}] Attaching MongoDB checkpointer to graph")
                    graph_reporter.checkpointer = checkpointer
                    graph_reporter.store = in_memory_store
                    logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
                    async for event in _stream_graph_events(
                        graph_reporter, workflow_input, workflow_config, thread_id
                    ):
                        yield event
                    logger.debug(f"[{safe_thread_id}] Graph event streaming completed")
        else:
            logger.debug(f"[{safe_thread_id}] No checkpointer configured, using in-memory graph")
            logger.debug(f"[{safe_thread_id}] Starting to stream graph events")
            async for event in _stream_graph_events(
                graph_reporter, workflow_input, workflow_config, thread_id
            ):
                yield event
            logger.debug(f"[{safe_thread_id}] Graph event streaming completed")
    finally:
        reset_runtime_llm_type(runtime_llm_token)


async def _astream_quest_chat_generator(request: QuestChatRequest):
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())
    request = request.model_copy(update={"thread_id": thread_id})
    message_id = "run--" + uuid4().hex
    agent_name = "quest_chat"
    full_answer = ""

    _process_initial_messages(
        {"id": uuid4().hex, "content": request.query},
        thread_id,
    )

    try:
        service = get_quest_service()
        references, context = await asyncio.to_thread(service.get_chat_context, request)

        if references:
            yield _make_event(
                "quest_references",
                {
                    "thread_id": thread_id,
                    "id": message_id,
                    "agent": agent_name,
                    "references": [
                        reference.model_dump() for reference in references
                    ],
                },
            )
        else:
            no_result_message = "在指定文件范围内未检索到足够依据，暂时无法回答这个问题。"
            service.remember_chat_turn(
                thread_id,
                request.query,
                no_result_message,
            )
            yield _make_event(
                "message_chunk",
                {
                    "thread_id": thread_id,
                    "id": message_id,
                    "agent": agent_name,
                    "role": "assistant",
                    "content": no_result_message,
                },
            )
            yield _make_event(
                "finish",
                {
                    "thread_id": thread_id,
                    "id": message_id,
                    "agent": agent_name,
                    "finish_reason": "finish",
                },
            )
            return

        async for chunk in service.astream_answer_with_context(
            thread_id,
            request.query,
            context,
        ):
            full_answer += chunk
            yield _make_event(
                "message_chunk",
                {
                    "thread_id": thread_id,
                    "id": message_id,
                    "agent": agent_name,
                    "role": "assistant",
                    "content": chunk,
                },
            )

        service.remember_chat_turn(
            thread_id,
            request.query,
            full_answer,
        )
        yield _make_event(
            "finish",
            {
                "thread_id": thread_id,
                "id": message_id,
                "agent": agent_name,
                "finish_reason": "finish",
            },
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Failed to stream quest chat: %s", exc)
        yield _make_event(
            "error",
            {
                "thread_id": thread_id,
                "id": message_id,
                "agent": agent_name,
                "info": f"Failed to stream quest chat: {exc}",
                "finish_reason": "finish",
            },
        )


def _make_event(event_type: str, data: dict[str, any]):
    if data.get("content") == "":
        data.pop("content")
    # Ensure JSON serialization with proper encoding
    try:
        json_data = json.dumps(data, ensure_ascii=False)

        finish_reason = data.get("finish_reason", "")
        chat_stream_message(
            data.get("thread_id", ""),
            f"event: {event_type}\ndata: {json_data}\n\n",
            finish_reason,
        )

        return f"event: {event_type}\ndata: {json_data}\n\n"
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing event data: {e}")
        # Return a safe error event
        error_data = json.dumps({"error": "Serialization failed"}, ensure_ascii=False)
        return f"event: error\ndata: {error_data}\n\n"


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using volcengine TTS API."""
    app_id = get_str_env("VOLCENGINE_TTS_APPID", "")
    if not app_id:
        raise HTTPException(status_code=400, detail="VOLCENGINE_TTS_APPID is not set")
    access_token = get_str_env("VOLCENGINE_TTS_ACCESS_TOKEN", "")
    if not access_token:
        raise HTTPException(
            status_code=400, detail="VOLCENGINE_TTS_ACCESS_TOKEN is not set"
        )

    try:
        cluster = get_str_env("VOLCENGINE_TTS_CLUSTER", "volcano_tts")
        voice_type = get_str_env("VOLCENGINE_TTS_VOICE_TYPE", "BV700_V2_streaming")

        tts_client = VolcengineTTS(
            appid=app_id,
            access_token=access_token,
            cluster=cluster,
            voice_type=voice_type,
        )
        # Call the TTS API
        result = tts_client.text_to_speech(
            text=request.text[:1024],
            encoding=request.encoding,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            text_type=request.text_type,
            with_frontend=request.with_frontend,
            frontend_type=request.frontend_type,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=str(result["error"]))

        # Decode the base64 audio data
        audio_data = base64.b64decode(result["audio_data"])

        # Return the audio file
        return Response(
            content=audio_data,
            media_type=f"audio/{request.encoding}",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=tts_output.{request.encoding}"
                )
            },
        )

    except Exception as e:
        logger.exception(f"Error in TTS endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/mcp/server/metadata", response_model=MCPServerMetadataResponse)
async def mcp_server_metadata(request: MCPServerMetadataRequest):
    """Get information about an MCP server."""
    # Check if MCP server configuration is enabled
    if not get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False):
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    try:
        # Set default timeout with a longer value for this endpoint
        timeout = 300  # Default to 300 seconds for this endpoint

        # Use custom timeout from request if provided
        if request.timeout_seconds is not None:
            timeout = request.timeout_seconds

        # Load tools from the MCP server using the utility function
        tools = await load_mcp_tools(
            server_type=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            timeout_seconds=timeout,
        )

        # Create the response with tools
        response = MCPServerMetadataResponse(
            transport=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            tools=tools,
        )

        return response
    except Exception as e:
        logger.exception(f"Error in MCP server metadata endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.get("/api/rag/config", response_model=RAGConfigResponse)
async def rag_config():
    """Get the config of the RAG."""
    return RAGConfigResponse(provider=SELECTED_RAG_PROVIDER)


@app.get("/api/rag/resources", response_model=RAGResourcesResponse)
async def rag_resources(request: Annotated[RAGResourceRequest, Query()]):
    """Get the resources of the RAG."""
    retriever = build_retriever()
    if retriever:
        return RAGResourcesResponse(resources=retriever.list_resources(request.query))
    return RAGResourcesResponse(resources=[])


@app.get("/api/config", response_model=ConfigResponse)
async def config():
    """Get the config of the server."""
    return ConfigResponse(
        rag=RAGConfigResponse(provider=SELECTED_RAG_PROVIDER),
        models=get_configured_llm_models(),
    )
