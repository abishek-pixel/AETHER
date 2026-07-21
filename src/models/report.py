"""ResearchReport ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.session import Base


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    key_findings: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    timeline_events: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    execution_time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped["ResearchSession"] = relationship(  # noqa: F821
        "ResearchSession", back_populates="report"
    )

    def __repr__(self) -> str:
        return f"<ResearchReport id={self.id} session_id={self.session_id}>"
