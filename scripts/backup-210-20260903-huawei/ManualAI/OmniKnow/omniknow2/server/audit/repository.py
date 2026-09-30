from typing import Optional, Sequence
from uuid import UUID

from fastapi import Request
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from audit.model import ActivityLog
from audit.schema import ActivityLogFilter


class AuditRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_log(
        self,
        user_id: Optional[UUID],
        action: str,
        space_id: Optional[UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None,
        detail: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActivityLog:
        """写入审计记录。

        内置 commit：业务逻辑后续失败时审计记录仍持久化。
        若调用方处于 ``async with session.begin()`` 上下文中，commit 会
        提前结束当前事务，begin() 退出时是空操作，不影响正确性。
        """
        log = ActivityLog(
            space_id=space_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.commit()
        return log

    async def create_log_from_request(
        self,
        request: Optional[Request],
        user_id: Optional[UUID],
        action: str,
        space_id: Optional[UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None,
        detail: Optional[dict] = None,
    ) -> ActivityLog:
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        return await self.create_log(
            space_id=space_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_by_id(self, log_id: UUID) -> Optional[ActivityLog]:
        result = await self.session.execute(
            select(ActivityLog).where(ActivityLog.uuid == log_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ActivityLog]:
        result = await self.session.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id)
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_by_target(
        self,
        target_type: str,
        target_id: UUID,
    ) -> Sequence[ActivityLog]:
        result = await self.session.execute(
            select(ActivityLog)
            .where(
                and_(
                    ActivityLog.target_type == target_type,
                    ActivityLog.target_id == target_id,
                )
            )
            .order_by(desc(ActivityLog.created_at))
        )
        return result.scalars().all()

    def _build_conditions(self, filters: ActivityLogFilter) -> list:
        conditions = []
        if filters.space_id:
            conditions.append(ActivityLog.space_id == filters.space_id)
        if filters.user_id:
            conditions.append(ActivityLog.user_id == filters.user_id)
        if filters.action:
            conditions.append(ActivityLog.action == filters.action)
        if filters.target_type:
            conditions.append(ActivityLog.target_type == filters.target_type)
        if filters.target_id:
            conditions.append(ActivityLog.target_id == filters.target_id)
        if filters.start_date:
            conditions.append(ActivityLog.created_at >= filters.start_date)
        if filters.end_date:
            conditions.append(ActivityLog.created_at <= filters.end_date)
        return conditions

    async def filter_logs(
        self,
        filters: ActivityLogFilter,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ActivityLog]:
        query = select(ActivityLog)
        conditions = self._build_conditions(filters)
        if conditions:
            query = query.where(and_(*conditions))
        query = (
            query.order_by(desc(ActivityLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_by_filters(self, filters: ActivityLogFilter) -> int:
        query = select(func.count(ActivityLog.uuid))
        conditions = self._build_conditions(filters)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return result.scalar() or 0
