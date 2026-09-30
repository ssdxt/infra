from typing import Optional
from uuid import UUID

from core.dependencies import RequestContext
from report.error import ReportNotExistedError
from report.repository import ReportRepository
from report.schema import ReportCreateSchema, ReportUpdateSchema


class ReportService:

    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.repo = ReportRepository(self.db)

    async def create_report(self, space_id: UUID, report_info: ReportCreateSchema):
        author_id = self.user.uuid
        async with self.db.begin():
            report = await self.repo.create_report(space_id, author_id, report_info)
        return self._serialize(report)

    async def get_report(self, space_id: UUID, report_id: UUID):
        report = await self.repo.get_report(space_id, report_id)
        if not report:
            raise ReportNotExistedError(report_id)
        return self._serialize(report)

    async def list_reports(
        self,
        space_id: UUID,
        page: int,
        page_size: int,
        keyword: Optional[str] = None,
    ):
        reports, total = await self.repo.get_reports(space_id, self.user.uuid, page, page_size, keyword)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "reports": [self._serialize(r) for r in reports],
        }

    async def update_report(self, space_id: UUID, report_id: UUID, report_info: ReportUpdateSchema):
        async with self.db.begin():
            report = await self.repo.update_report(space_id, report_id, report_info)
        if not report:
            return None
        return self._serialize(report)

    async def delete_report(self, space_id: UUID, report_id: UUID):
        async with self.db.begin():
            ok = await self.repo.delete_report(space_id, report_id)
        return ok

    @staticmethod
    def _serialize(report) -> dict:
        return {
            "uuid": str(report.uuid),
            "title": report.title,
            "content": report.content,
            "type": report.type,
            "author_id": str(report.author_id) if report.author_id else None,
            "extra": report.extra,
            "created_at": report.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": report.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
