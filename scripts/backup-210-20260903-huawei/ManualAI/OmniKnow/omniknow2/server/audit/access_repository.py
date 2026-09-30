from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from audit.access_model import AccessLog
from db.session import async_session


class AccessLogRepository:

    @staticmethod
    async def create(
        user_id: Optional[UUID],
        space_id: Optional[UUID],
        method: str,
        path: str,
        status_code: Optional[int],
        duration_ms: Optional[int],
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """独立 session 写入 —— 避免与请求 session 争用，失败静默"""
        try:
            async with async_session() as session:  # type: AsyncSession
                session.add(AccessLog(
                    user_id=user_id,
                    space_id=space_id,
                    method=method,
                    path=path[:255] if path else path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    ip_address=ip_address,
                    user_agent=user_agent,
                ))
                await session.commit()
        except Exception:
            from utils.log import logger
            logger.exception("AccessLog 写入失败")
