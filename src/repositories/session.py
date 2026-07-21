"""ResearchSession repository — all DB operations return plain dicts to avoid
lazy-load errors when accessed outside an async SQLAlchemy context."""
import uuid
from datetime import timezone
from sqlalchemy import select, delete, update, desc, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.session import ResearchSession


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _safe_iso(dt) -> str:
        """Convert a datetime to ISO string, returning empty string on failure."""
        try:
            return dt.isoformat()
        except Exception:
            return ""

    @staticmethod
    def _row_to_dict(s: ResearchSession, include_report: bool = True) -> dict:
        """Convert an ORM row to a plain dict BEFORE the session is closed.
        
        All attribute access must happen here while the session is still open.
        Do NOT call this after await db.commit() / await db.close().
        """
        report = None
        if include_report:
            try:
                r = s.report
                if r is not None:
                    report = {
                        "title": r.title,
                        "summary": r.summary,
                        "main_content": r.main_content,
                        "citations": r.citations or [],
                        "key_findings": r.key_findings or [],
                        "confidence_score": r.confidence_score,
                        "execution_time": r.execution_time,
                        "cost": r.cost,
                        "timeline_events": r.timeline_events or [],
                    }
            except Exception:
                report = None

        return {
            "id": str(s.id),
            "title": s.title,
            "query": s.query,
            "status": s.status,
            "depth": s.depth,
            "model": s.model,
            "created_at": SessionRepository._safe_iso(s.created_at),
            "updated_at": SessionRepository._safe_iso(s.updated_at),
            "report": report,
        }

    # ── Write operations ─────────────────────────────────────────────────

    async def create(
        self,
        user_id: uuid.UUID,
        query: str,
        depth: str = "balanced",
        model: str = "llama-3.3-70b-versatile",
    ) -> dict:
        """Create a new session and return its dict representation."""
        title = query[:120]
        session = ResearchSession(
            user_id=user_id, title=title, query=query,
            depth=depth, model=model, status="running",
        )
        self.db.add(session)
        await self.db.flush()
        # Read all values immediately — flush keeps the session alive here
        sid        = str(session.id)
        created_at = self._safe_iso(session.created_at)
        updated_at = self._safe_iso(session.updated_at)
        return {
            "id": sid,
            "title": title,
            "query": query,
            "status": "running",
            "depth": depth,
            "model": model,
            "created_at": created_at,
            "updated_at": updated_at,
            "report": None,
        }

    async def rename(self, session_id: uuid.UUID, user_id: uuid.UUID, title: str) -> dict | None:
        """Rename a session. Returns the updated dict or None if not found."""
        result = await self.db.execute(
            select(ResearchSession)
            .where(ResearchSession.id == session_id, ResearchSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None

        # Capture values BEFORE flush (flush expires the ORM instance)
        sid        = str(session.id)
        query      = session.query
        status     = session.status
        depth      = session.depth
        model      = session.model
        created_at = self._safe_iso(session.created_at)
        new_title  = title[:120]

        session.title = new_title
        await self.db.flush()

        return {
            "id": sid,
            "title": new_title,
            "query": query,
            "status": status,
            "depth": depth,
            "model": model,
            "created_at": created_at,
            "updated_at": created_at,
            "report": None,
        }

    async def update_status(self, session_id: uuid.UUID, status: str) -> None:
        """Update session status via a bulk UPDATE (no ORM expiry issue)."""
        await self.db.execute(
            update(ResearchSession)
            .where(ResearchSession.id == session_id)
            .values(status=status)
        )

    async def delete(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            delete(ResearchSession)
            .where(ResearchSession.id == session_id, ResearchSession.user_id == user_id)
        )
        return result.rowcount > 0

    # ── Read operations ──────────────────────────────────────────────────

    async def get_by_id(self, session_id: uuid.UUID) -> ResearchSession | None:
        """Return ORM object (used internally by main.py workflow)."""
        result = await self.db.execute(
            select(ResearchSession)
            .where(ResearchSession.id == session_id)
            .options(selectinload(ResearchSession.report))
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        result = await self.db.execute(
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(desc(ResearchSession.updated_at))
            .limit(limit)
            .offset(offset)
            .options(selectinload(ResearchSession.report))
        )
        # Convert to dicts WHILE the session is still open
        return [self._row_to_dict(s) for s in result.scalars().all()]

    async def get_by_id_for_user(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict | None:
        result = await self.db.execute(
            select(ResearchSession)
            .where(ResearchSession.id == session_id, ResearchSession.user_id == user_id)
            .options(
                selectinload(ResearchSession.messages),
                selectinload(ResearchSession.report),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None

        # Build full dict including messages — all inside the open session
        # Order messages chronologically so blocks are built in correct order
        d = self._row_to_dict(session, include_report=True)
        d["messages"] = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "timestamp": self._safe_iso(m.timestamp),
            }
            for m in sorted(session.messages, key=lambda m: m.timestamp)
        ]
        return d

    async def search(self, user_id: uuid.UUID, q: str, limit: int = 20) -> list[dict]:
        result = await self.db.execute(
            select(ResearchSession)
            .where(
                ResearchSession.user_id == user_id,
                or_(
                    ResearchSession.title.ilike(f"%{q}%"),
                    ResearchSession.query.ilike(f"%{q}%"),
                ),
            )
            .order_by(desc(ResearchSession.updated_at))
            .limit(limit)
            .options(selectinload(ResearchSession.report))
        )
        return [self._row_to_dict(s) for s in result.scalars().all()]
