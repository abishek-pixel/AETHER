"""Feedback router."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_active_user
from src.database.session import get_db
from src.repositories.session import SessionRepository
from src.models.feedback import Feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    session_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id_for_user(body.session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    fb = Feedback(session_id=body.session_id, rating=body.rating, comment=body.comment)
    db.add(fb)
    await db.flush()
    await db.commit()
    return {"id": str(fb.id), "status": "saved"}
