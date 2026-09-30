from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import Request

from audit.repository import AuditRepository
from audit.schema import ActivityLogFilter, ActivityLogResponse


class AuditService:

    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def log(
        self,
        user_id: Optional[UUID],
        action: str,
        space_id: Optional[UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None,
        detail: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActivityLogResponse:
        log = await self.repo.create_log(
            space_id=space_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return ActivityLogResponse.model_validate(log)

    async def log_from_request(
        self,
        request: Request,
        user_id: Optional[UUID],
        action: str,
        space_id: Optional[UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> ActivityLogResponse:
        log = await self.repo.create_log_from_request(
            request=request,
            space_id=space_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        return ActivityLogResponse.model_validate(log)

    async def get_log(self, log_id: UUID) -> Optional[ActivityLogResponse]:
        log = await self.repo.get_by_id(log_id)
        return ActivityLogResponse.model_validate(log) if log else None

    async def get_user_logs(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ActivityLogResponse]:
        logs = await self.repo.get_by_user(user_id, limit, offset)
        return [ActivityLogResponse.model_validate(x) for x in logs]

    async def get_target_history(
        self,
        target_type: str,
        target_id: UUID,
    ) -> List[ActivityLogResponse]:
        logs = await self.repo.get_by_target(target_type, target_id)
        return [ActivityLogResponse.model_validate(x) for x in logs]

    async def search_logs(
        self,
        filters: ActivityLogFilter,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[ActivityLogResponse], int]:
        items = await self.repo.filter_logs(filters, limit, offset)
        total = await self.repo.count_by_filters(filters)
        return [ActivityLogResponse.model_validate(x) for x in items], total

    async def get_user_statistics(
        self,
        user_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        return await self.get_user_statistics_in_space(user_id, space_id=None, days=days)

    async def get_user_statistics_in_space(
        self,
        user_id: UUID,
        space_id: Optional[UUID],
        days: int = 30,
    ) -> Dict[str, Any]:
        start_date = datetime.utcnow() - timedelta(days=days)
        filters = ActivityLogFilter(space_id=space_id, user_id=user_id, start_date=start_date)
        logs = await self.repo.filter_logs(filters, limit=10000)

        action_counts: Dict[str, int] = {}
        target_counts: Dict[str, int] = {}
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
            if log.target_type:
                target_counts[log.target_type] = target_counts.get(log.target_type, 0) + 1

        return {
            "user_id": user_id,
            "space_id": space_id,
            "period_days": days,
            "total_actions": len(logs),
            "action_breakdown": action_counts,
            "target_breakdown": target_counts,
            "start_date": start_date,
            "end_date": datetime.utcnow(),
        }
