from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from report.error import ReportNotExistedError
from report.models import Report
from db.models.rag import Resource, KnowledgeBase
from report.schema import ReportCreateSchema, ReportUpdateSchema
from core.acl.schema import ResourceStatus


class ReportRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_kbase_files_list(self, collection_name: str):
        kbase_obj = await self.session.execute(
            select(KnowledgeBase).where(KnowledgeBase.collection_name == collection_name)
        )
        kbase = kbase_obj.scalar_one_or_none()
        result = await self.session.execute(
            select(Resource).where(Resource.kbase_id == kbase.uuid, Resource.status != ResourceStatus.destroyed)
        )
        return result.scalars().all()

    async def create_report(self, space_id: UUID, author_id: UUID, report: ReportCreateSchema) -> Report:
        report = Report(
            space_id=space_id,
            author_id=author_id,
            title=report.title,
            content=report.content,
            type=report.type,
            extra=report.extra,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_report(self, space_id: UUID, report_id: UUID) -> Report | None:
        result = await self.session.execute(
            select(Report).where(Report.space_id == space_id, Report.uuid == report_id, Report.status == 1)
        )
        return result.scalar_one_or_none()

    async def get_reports(
        self,
        space_id: UUID,
        user_id: UUID,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ):
        offset = (page - 1) * page_size
        conditions = [
            Report.space_id == space_id,
            Report.author_id == user_id,
            Report.status == 1,
        ]
        if keyword:
            conditions.append(
                or_(
                    Report.title.ilike(f"%{keyword}%"),
                    Report.content.ilike(f"%{keyword}%"),
                )
            )

        result = await self.session.execute(
            select(Report)
            .where(*conditions)
            .order_by(Report.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        reports = result.scalars().all()

        count_result = await self.session.execute(
            select(func.count(Report.uuid))
            .where(*conditions)
        )
        total = count_result.scalar() or 0
        return reports, total

    async def update_report(self, space_id, report_id: UUID, report_info: ReportUpdateSchema) -> Report | None:
        result = await self.session.execute(
            select(Report).where(Report.space_id == space_id, Report.uuid == report_id, Report.status == 1)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise ReportNotExistedError(report_id)
        updates = report_info.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(report, key, value)
        await self.session.flush()
        return report

    async def delete_report(self, space_id: UUID, report_id: UUID) -> bool:
        result = await self.session.execute(
            select(Report).where(Report.space_id == space_id, Report.uuid == report_id, Report.status == 1)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise ReportNotExistedError
        report.status = 0
        await self.session.flush()
        return True
