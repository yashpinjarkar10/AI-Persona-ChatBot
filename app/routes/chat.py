from __future__ import annotations

import json
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.schema.chat import ChatRequest, StartResponse
from app.services.rag import (
    fetch_relevant_docs,
    generate_llm_response,
    input_guardrail,
    judge_grounding,
    output_guardrail,
    should_use_knowledge_base,
)
from app.services.supabase_client import get_supabase

router = APIRouter()


def _create_session(session_id: str | None = None) -> str:
    """Return existing or new session ID."""
    return session_id or str(uuid4())


def _validate_session_id(session_id: str) -> str:
    """Validate UUID session IDs before using them in Supabase queries."""
    try:
        return str(UUID(session_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="session_id must be a valid UUID")


def _load_history(session_id: str) -> list[HumanMessage | AIMessage]:
    """Fetch recent chat exchanges for a session from Supabase chat_history table."""
    resp = (
        get_supabase()
        .table("chat_history")
        .select("user_query, llm_response")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(10)
        .execute()
    )
    messages: list[HumanMessage | AIMessage] = []
    for row in (resp.data or []):
        messages.append(HumanMessage(content=row["user_query"]))
        messages.append(AIMessage(content=row["llm_response"]))
    return messages


def _save_exchange(session_id: str, user_query: str, fetched_docs: list[str], llm_response: str) -> None:
    """Save user query, retrieved docs, and LLM response to Supabase chat_history table."""
    get_supabase().table("chat_history").insert({
        "session_id": session_id,
        "user_query": user_query,
        "fetched_docs": fetched_docs,
        "llm_response": llm_response,
    }).execute()


@router.get("/")
async def root():
    """Health check root endpoint."""
    return {"message": "FastAPI Server is Running!"}


@router.post("/start", response_model=StartResponse)
async def start_chat():
    """Create a new chat session."""
    session_id = _create_session()
    return StartResponse(session_id=session_id, message="Chat session started.")


@router.post("/chat")
async def chat(chat_request: ChatRequest):
    """Handle chat request through input guardrail, Supabase RAG, LLM, output guardrail, and LLM judge."""
    query = chat_request.input.strip()
    if query.lower() == "exit":
        raise HTTPException(status_code=400, detail="Use /start to reset the chat session.")

    session_id = _validate_session_id(chat_request.session_id) if chat_request.session_id else _create_session()

    async def stream_pipeline():
        # 1. Input Security Guardrail
        is_safe, error_msg = input_guardrail(query)
        if not is_safe:
            yield f"data: {json.dumps({'error': error_msg, 'answer': error_msg})}\n\n"
            return

        yield f"data: {json.dumps({'status': 'Understanding query...'})}\n\n"
        history = _load_history(session_id)
        use_knowledge_base = should_use_knowledge_base(query)
        docs: list[str] = []

        # 2. Search Knowledge Base only when the query needs factual grounding.
        if use_knowledge_base:
            yield f"data: {json.dumps({'status': 'Searching knowledge base...'})}\n\n"
            docs = fetch_relevant_docs(query)

        # 3. Generating Response Status
        yield f"data: {json.dumps({'status': 'Generating response...'})}\n\n"
        try:
            raw_response = generate_llm_response(query, history, docs)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'answer': 'An error occurred while generating the response.'})}\n\n"
            return

        # 4. Validating Response Status
        yield f"data: {json.dumps({'status': 'Validating response...'})}\n\n"
        is_valid_output, output_error = output_guardrail(query, raw_response)
        if not is_valid_output:
            final_response = output_error
        else:
            is_grounded = not use_knowledge_base or judge_grounding(query, raw_response, docs)
            if not is_grounded:
                final_response = "I don't have enough specific information in my knowledge base to answer that accurately."
            else:
                final_response = raw_response

        # 5. Persist to Supabase chat_history table
        try:
            _save_exchange(session_id, query, docs, final_response)
        except Exception:
            pass

        # 6. Return Final Response
        yield f"data: {json.dumps({'answer': final_response, 'session_id': session_id})}\n\n"

    return StreamingResponse(
        stream_pipeline(),
        media_type="text/event-stream",
        headers={"X-Session-Id": session_id},
    )
