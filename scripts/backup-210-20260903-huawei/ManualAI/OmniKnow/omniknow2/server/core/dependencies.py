# dependencies/auth.py
from uuid import UUID
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from fastapi import Depends, Request

from db.session import get_session
from exceptions.errors.resource import ResourcePermissionError
from schemas.user import CurrentUser
from core.security import check_auth_credentials
from ext.redis_client import get_redis
from core.acl.acl import ACL
from core.acl.schema import Action
from core.rbac import check_rbac
from audit.spec import AuditSpec, write_audit


class RequestContext:
    def __init__(self, user, db, redis, request: Request = None):
        self.user = user
        self.db = db
        self.redis = redis
        self.request = request

    @property
    def audit_detail(self) -> Optional[dict]:
        if self.request is None:
            return None
        return getattr(self.request.state, "audit_detail", None)

    @audit_detail.setter
    def audit_detail(self, value: Optional[dict]) -> None:
        if self.request is not None:
            self.request.state.audit_detail = value


async def check_resource_permission(user_id: UUID, space_id: UUID, resource_id: UUID, resource_type: str, action: Action, session: AsyncSession):
    acl = ACL(session)
    if not await acl.check_acl(user_id=user_id, space_id=space_id, resource_type=resource_type, resource_id=resource_id,
                               action=action):
        raise ResourcePermissionError(resource_type, resource_id, action)


def authorize(
    permission_code: str = "public",
    *,
    audit: Optional[AuditSpec] = None,
) -> Callable:
    """
    权限校验 + 请求上下文。
    传入 audit=AuditSpec(...) 时，请求完成后自动写入 ActivityLog。
    target_id/space_id 从 path_params 自动推断；
    service 层可通过 ctx.audit_detail = {...} 扩展 detail，
    或以 {"_target_id": UUID} 覆写 target_id（用于创建型接口）。
    """

    async def dependency(
            request: Request,
            user: CurrentUser = Depends(check_auth_credentials),
            db: AsyncSession = Depends(get_session),
            redis: Redis = Depends(get_redis)
    ):
        await check_rbac(user, permission_code, redis, db)
        ctx = RequestContext(user=user, db=db, redis=redis, request=request)
        if audit is None:
            yield ctx
            return
        try:
            yield ctx
        except Exception as e:
            await write_audit(ctx, audit, request, success=False, error=type(e).__name__)
            raise
        else:
            await write_audit(ctx, audit, request, success=True)

    return dependency


async def get_request_context(
        request: Request,
        user: CurrentUser = Depends(check_auth_credentials),
        db: AsyncSession = Depends(get_session),
        redis: Redis = Depends(get_redis)
) -> RequestContext:
    return RequestContext(user=user, db=db, redis=redis, request=request)


def audited(audit: AuditSpec) -> Callable:
    """无 RBAC 检查的审计依赖（ACL 由 service 层处理）"""

    async def dependency(
            request: Request,
            user: CurrentUser = Depends(check_auth_credentials),
            db: AsyncSession = Depends(get_session),
            redis: Redis = Depends(get_redis),
    ):
        ctx = RequestContext(user=user, db=db, redis=redis, request=request)
        try:
            yield ctx
        except Exception as e:
            await write_audit(ctx, audit, request, success=False, error=type(e).__name__)
            raise
        else:
            await write_audit(ctx, audit, request, success=True)

    return dependency


# def get_rabbitmq(request: Request) -> RabbitMQClient:
#     return cast(RabbitMQClient, request.app.state.rabbitmq)


# def require_permission(permission_code: str) -> Callable:
#     async def dependency(
#         user: CurrentUser = Depends(check_auth_credentials),
#         redis: Redis = Depends(get_redis)
#     ):
#         key = f"user_permissions:{user.uuid}"
#         has_permission = await redis.sismember(key, permission_code)
#         if not has_permission:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Permission denied"
#             )
#     return dependency
