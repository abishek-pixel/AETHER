"""Sessions router — CRUD for research sessions."""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_active_user
from src.database.session import get_db
from src.repositories.session import SessionRepository
from src.repositories.usage import UsageRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Schemas ────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    query: str
    depth: str = "balanced"
    model: str = "llama-3.3-70b-versatile"


class SessionRename(BaseModel):
    title: str


class ReportOut(BaseModel):
    title: str | None
    summary: str | None
    main_content: str | None
    citations: list
    key_findings: list
    confidence_score: float
    execution_time: float
    cost: float

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str

    class Config:
        from_attributes = True


class SessionOut(BaseModel):
    id: str
    title: str
    query: str
    status: str
    depth: str
    model: str
    created_at: str
    updated_at: str
    report: ReportOut | None = None

    class Config:
        from_attributes = True


class SessionDetailOut(SessionOut):
    messages: list[MessageOut] = []


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_session(s) -> dict:
    # Access report safely — it may not be loaded if selectinload wasn't used
    try:
        report = _fmt_report(s.report) if s.report else None
    except Exception:
        report = None
    return {
        "id": str(s.id),
        "title": s.title,
        "query": s.query,
        "status": s.status,
        "depth": s.depth,
        "model": s.model,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
        "report": report,
    }


def _fmt_report(r) -> dict | None:
    if r is None:
        return None
    return {
        "title": r.title,
        "summary": r.summary,
        "main_content": r.main_content,
        "citations": r.citations or [],
        "key_findings": r.key_findings or [],
        "confidence_score": r.confidence_score,
        "execution_time": r.execution_time,
        "cost": r.cost,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("", summary="List user's research sessions")
async def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Search query"),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = SessionRepository(db)
    if q:
        sessions = await repo.search(current_user.id, q)
    else:
        sessions = await repo.list_for_user(current_user.id, limit=limit, offset=offset)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/{session_id}", summary="Get a single session with messages and report")
async def get_session(
    session_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = SessionRepository(db)
    data = await repo.get_by_id_for_user(session_id, current_user.id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return data


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a new session record")
async def create_session(
    body: SessionCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = SessionRepository(db)
    result = await repo.create(
        user_id=current_user.id,
        query=body.query,
        depth=body.depth,
        model=body.model,
    )
    await db.commit()
    return result


@router.patch("/{session_id}/rename", summary="Rename a session")
async def rename_session(
    session_id: uuid.UUID,
    body: SessionRename,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = SessionRepository(db)
    result = await repo.rename(session_id, current_user.id, body.title)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.commit()
    return result


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a session")
async def delete_session(
    session_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = SessionRepository(db)
    deleted = await repo.delete(session_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.commit()
    return None
