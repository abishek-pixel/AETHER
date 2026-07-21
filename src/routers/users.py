"""Users router — profile and usage/analytics endpoints."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_active_user
from src.database.session import get_db
from src.repositories.user import UserRepository
from src.repositories.usage import UsageRepository
from src.repositories.session import SessionRepository
from src.models.subscription import Subscription

router = APIRouter(prefix="/users", tags=["users"])


# ── Schemas ────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)


class ProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    created_at: str


class SubscriptionResponse(BaseModel):
    current_plan: str
    credits_remaining: int
    renewal_date: str | None


class UsageDashboardResponse(BaseModel):
    total_tokens: int
    total_cost: float
    total_sessions: int
    total_requests: int
    credits_remaining: int
    current_plan: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/me/profile", response_model=ProfileResponse)
async def get_profile(
    current_user=Depends(get_current_active_user),
):
    """Return the authenticated user's profile."""
    return ProfileResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        plan=current_user.plan,
        created_at=current_user.created_at.isoformat(),
    )


@router.patch("/me/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's name."""
    repo = UserRepository(db)
    user = await repo.update_name(current_user.id, body.name.strip())
    await db.commit()
    return ProfileResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        plan=user.plan,
        created_at=user.created_at.isoformat(),
    )


@router.get("/me/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return subscription and credits info."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return SubscriptionResponse(
        current_plan=sub.current_plan,
        credits_remaining=sub.credits_remaining,
        renewal_date=sub.renewal_date.isoformat() if sub.renewal_date else None,
    )


@router.get("/me/usage", response_model=UsageDashboardResponse)
async def get_usage_dashboard(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return total token usage, cost, and session count for the dashboard."""
    usage_repo = UsageRepository(db)
    session_repo = SessionRepository(db)

    totals = await usage_repo.get_totals_for_user(current_user.id)
    sessions = await session_repo.list_for_user(current_user.id, limit=1000)

    # Get subscription credits
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    credits = sub.credits_remaining if sub else 0
    plan = sub.current_plan if sub else "free"

    return UsageDashboardResponse(
        total_tokens=totals["total_tokens"],
        total_cost=round(totals["total_cost"], 6),
        total_sessions=len(sessions),
        total_requests=totals["total_requests"],
        credits_remaining=credits,
        current_plan=plan,
    )
