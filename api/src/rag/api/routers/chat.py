import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from rag.db.session import get_db
from rag.rag.chat_service import ChatService, ConversationNotFoundError

router = APIRouter(prefix="/conversations", tags=["chat"])


class MessageRequest(BaseModel):
    content: str


@router.post("")
async def create_conversation(db: AsyncSession = Depends(get_db)) -> dict:
    result = await ChatService().create_conversation(db)
    return {"conversation_id": str(result.conversation_id)}


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await ChatService().send_message(conversation_id, body.content, db)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "message_id": str(result.message_id) if result.message_id else None,
        "role": result.role,
        "content": result.content,
        "sources": result.sources,
    }


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        items = await ChatService().list_messages(conversation_id, db)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return [
        {
            "message_id": str(item.message_id),
            "role": item.role,
            "content": item.content,
            "sources": item.sources,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]
