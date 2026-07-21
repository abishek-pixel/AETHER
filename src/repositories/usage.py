"""UsageLog repository — rate-limiting for free-tier users."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.usage import UsageLog

# ── Free-tier limits ───────────────────────────────────────────────────────
FREE_TIER_PROMPT_LIMIT = 2
FREE_TIER_WINDOW_HOURS = 6


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class UsageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Token / cost logging ───────────────────────────────────────────────

    async def log(
        self,
        user_id: uuid.UUID,
        session_id: Optional[uuid.UUID],
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
    ) -> UsageLog:
        entry = UsageLog(
            user_id=user_id,
            session_id=session_id,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost=estimated_cost,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_totals_for_user(self, user_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(UsageLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(UsageLog.estimated_cost), 0.0).label("total_cost"),
                func.count(UsageLog.id).label("total_requests"),
            ).where(UsageLog.user_id == user_id)
        )
        row = result.one()
        return {
            "total_tokens": int(row.total_tokens),
            "total_cost": float(row.total_cost),
            "total_requests": int(row.total_requests),
        }

    # ── Rate-limit helpers ─────────────────────────────────────────────────

    async def count_prompts_in_window(
        self,
        user_id: uuid.UUID,
        hours: int = FREE_TIER_WINDOW_HOURS,
    ) -> dict:
        """
        Count all chargeable research prompts (initial + follow-up) within the
        rolling N-hour window.

        We track prompts via ResearchSession rows (one per initial prompt) PLUS
        assistant messages beyond the first per session (each = one follow-up).

        Returns:
          prompts_used    — total prompts in window
          prompts_allowed — FREE_TIER_PROMPT_LIMIT
          remaining       — prompts left (0 if limited)
          reset_at        — ISO UTC when oldest prompt falls outside the window
          retry_after_seconds — seconds until reset (0 if not limited)
        """
        from src.models.session import ResearchSession as SessionModel
        from src.models.message import Message

        window_start = _utcnow() - timedelta(hours=hours)

        # Count initial sessions in window
        sess_result = await self.db.execute(
            select(func.count(SessionModel.id)).where(
                SessionModel.user_id == user_id,
                SessionModel.created_at >= window_start,
            )
        )
        session_count = sess_result.scalar() or 0

        # Count follow-up assistant messages in window
        # Each follow-up produces one assistant message linked to a session
        # belonging to this user, created after the session itself.
        followup_result = await self.db.execute(
            select(func.count(Message.id))
            .join(SessionModel, Message.session_id == SessionModel.id)
            .where(
                SessionModel.user_id == user_id,
                Message.role == "assistant",
                Message.timestamp >= window_start,
            )
        )
        followup_msg_count = followup_result.scalar() or 0

        # Total = one per session (initial prompt) + one per assistant reply (follow-up)
        # But the first assistant reply is the initial research result, not a follow-up.
        # So we subtract one assistant message per session to avoid double-counting.
        # Net follow-ups = max(0, assistant_msgs - initial_sessions_in_window)
        net_followups = max(0, followup_msg_count - session_count)
        total_prompts = session_count + net_followups

        # Oldest prompt timestamp (for reset_at calculation)
        oldest_sess = await self.db.execute(
            select(func.min(SessionModel.created_at)).where(
                SessionModel.user_id == user_id,
                SessionModel.created_at >= window_start,
            )
        )
        oldest_ts = oldest_sess.scalar()

        reset_at: Optional[str] = None
        retry_after_seconds: int = 0
        if oldest_ts:
            # oldest_ts from PostgreSQL may be offset-aware; normalise to UTC
            if oldest_ts.tzinfo is None:
                oldest_ts = oldest_ts.replace(tzinfo=timezone.utc)
            reset_dt = oldest_ts + timedelta(hours=hours)
            reset_at = reset_dt.isoformat()
            diff = (reset_dt - _utcnow()).total_seconds()
            retry_after_seconds = max(0, int(diff))

        remaining = max(0, FREE_TIER_PROMPT_LIMIT - total_prompts)

        return {
            "prompts_used": total_prompts,
            "prompts_allowed": FREE_TIER_PROMPT_LIMIT,
            "remaining": remaining,
            "reset_at": reset_at,
            "retry_after_seconds": retry_after_seconds,
        }

    async def check_and_reserve_prompt(
        self,
        user_id: uuid.UUID,
        hours: int = FREE_TIER_WINDOW_HOURS,
    ) -> dict:
        """
        Atomically check the rate-limit and reserve a prompt slot using a
        database-level advisory lock to prevent race conditions.

        Returns the same shape as count_prompts_in_window but with:
          allowed — True if the request is allowed, False if blocked
        """
        # Use PostgreSQL advisory lock keyed on the user_id to serialise
        # concurrent requests for the same user (avoids TOCTOU race condition).
        # Convert UUID to a stable 64-bit integer via its int property.
        lock_key = user_id.int % (2**63)
        await self.db.execute(
            text(f"SELECT pg_advisory_xact_lock({lock_key})")
        )

        info = await self.count_prompts_in_window(user_id, hours)
        info["allowed"] = info["prompts_used"] < FREE_TIER_PROMPT_LIMIT
        return info
