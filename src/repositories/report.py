"""ResearchReport repository."""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.report import ResearchReport


class ReportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(
        self,
        session_id: uuid.UUID,
        title: str | None,
        summary: str | None,
        main_content: str | None,
        citations: list,
        key_findings: list,
        confidence_score: float,
        execution_time: float,
        cost: float,
        timeline_events: list | None = None,
    ) -> ResearchReport:
        result = await self.db.execute(
            select(ResearchReport).where(ResearchReport.session_id == session_id)
        )
        report = result.scalar_one_or_none()

        if report:
            report.title = title
            report.summary = summary
            report.main_content = main_content
            report.citations = citations
            report.key_findings = key_findings
            report.confidence_score = confidence_score
            report.execution_time = execution_time
            report.cost = cost
            if timeline_events is not None:
                report.timeline_events = timeline_events
        else:
            report = ResearchReport(
                session_id=session_id,
                title=title,
                summary=summary,
                main_content=main_content,
                citations=citations,
                key_findings=key_findings,
                confidence_score=confidence_score,
                execution_time=execution_time,
                cost=cost,
                timeline_events=timeline_events or [],
            )
            self.db.add(report)

        await self.db.flush()
        return report

    async def get_by_session(self, session_id: uuid.UUID) -> ResearchReport | None:
        result = await self.db.execute(
            select(ResearchReport).where(ResearchReport.session_id == session_id)
        )
        return result.scalar_one_or_none()
