"""Messages router."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_active_user
from src.database.session import get_db
from src.repositories.message import MessageRepository
from src.repositories.session import SessionRepository

router = APIRouter(prefix="/messages", tags=["messages"])


class MessageCreate(BaseModel):
    session_id: uuid.UUID
    role: str
    content: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_message(
    body: MessageCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session belongs to user
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id_for_user(body.session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msg_repo = MessageRepository(db)
    msg = await msg_repo.create(body.session_id, body.role, body.content)
    await db.commit()
    return {
        "id": str(msg.id),
        "session_id": str(msg.session_id),
        "role": msg.role,
        "content": msg.content,
        "timestamp": msg.timestamp.isoformat(),
    }


@router.get("/{session_id}")
async def get_messages(
    session_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id_for_user(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msg_repo = MessageRepository(db)
    messages = await msg_repo.list_for_session(session_id)
    return {
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ]
    }
