from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(
        default=None,
        description="Optional session ID. If omitted, a new session is created automatically.",
    )


class StartResponse(BaseModel):
    session_id: str
    message: str
