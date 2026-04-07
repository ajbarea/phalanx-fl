"""
Assistant chat endpoint for IntelliFL.

Placeholder implementation - will be replaced with Dima's FL Agent integration.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatMessage(BaseModel):
    """A single message in the chat conversation."""

    role: str
    content: list[dict]


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    message: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message and return a response.

    TODO: Replace with FL Agent integration:
    - Ollama (RIT SPORC, gpt-oss-120b) for free tier
    - Celery for async long-running queries
    """
    last_msg = ""
    if request.messages:
        content = request.messages[-1].content
        if content and isinstance(content, list) and len(content) > 0:
            last_msg = content[0].get("text", "")

    return ChatResponse(message=f"[IntelliFL Assistant] You said: {last_msg}")
