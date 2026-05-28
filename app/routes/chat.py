from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.schema.chat import ChatRequest, StartResponse
from app.services.rag import get_rag_chain
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers — Supabase chat history
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS = 20  # load last N exchanges to keep context window manageable


def _create_session(session_id: str | None = None) -> str:
    """Insert a new row in chat_sessions and return its id."""
    sid = session_id or str(uuid4())
    sb = get_supabase()
    sb.table("chat_sessions").insert({"id": sid}).execute()
    return sid


def _load_history(session_id: str) -> list[HumanMessage | AIMessage]:
    """Fetch the most recent messages for a session from Supabase."""
    sb = get_supabase()
    resp = (
        sb.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(MAX_HISTORY_TURNS * 2)
        .execute()
    )
    messages: list[HumanMessage | AIMessage] = []
    for row in resp.data:
        if row["role"] == "human":
            messages.append(HumanMessage(content=row["content"]))
        else:
            messages.append(AIMessage(content=row["content"]))
    return messages


def _save_exchange(session_id: str, user_msg: str, ai_msg: str) -> None:
    """Persist a user–assistant exchange to Supabase."""
    sb = get_supabase()
    sb.table("chat_messages").insert(
        [
            {"session_id": session_id, "role": "human", "content": user_msg},
            {"session_id": session_id, "role": "ai", "content": ai_msg},
        ]
    ).execute()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/")
async def root():
    return {"message": "FastAPI Server is Running!"}


@router.post("/start", response_model=StartResponse)
async def start_chat():
    """Create a new chat session. Returns a session_id to use in /chat."""
    session_id = _create_session()
    logger.info("New chat session created: %s", session_id)
    return StartResponse(
        session_id=session_id,
        message="Chat session started.",
    )


@router.post("/chat")
async def chat(chat_request: ChatRequest):
    query = chat_request.input
    if query.lower() == "exit":
        raise HTTPException(status_code=400, detail="Use /start to reset the chat session.")

    # Auto-create a session if the caller didn't supply one
    session_id = chat_request.session_id
    if not session_id:
        session_id = _create_session()

    # Load history from Supabase
    history = _load_history(session_id)
    rag_chain = get_rag_chain()

    async def generate_response():
        full_response = ""
        try:
            async for chunk in rag_chain.astream({"input": query, "chat_history": history}):
                if "answer" in chunk:
                    piece = chunk["answer"]
                    full_response += piece
                    yield piece
        except Exception as e:
            logger.exception("Error during RAG streaming for session %s", session_id)
            yield f"\n\n[Error: {e}]"
            return

        # Persist the exchange to Supabase
        try:
            _save_exchange(session_id, query, full_response)
        except Exception:
            logger.exception("Failed to save exchange to Supabase for session %s", session_id)

    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
        headers={"X-Session-Id": session_id},
    )
