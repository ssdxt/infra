from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from audit.repository import AuditRepository
from audit.schema import ActivityLogFilter
from audit.service import AuditService
from core.acl.acl import ACL
from core.dependencies import RequestContext, authorize, get_request_context
from exceptions.errors.resource import SpaceAccessError
from schemas.public import ResponseModel


router = APIRouter()

admin_router = APIRouter(prefix="/admin/audit")
space_router = APIRouter(prefix="/spaces/{space_id}/audit")


def _service(ctx: RequestContext) -> AuditService:
    return AuditService(AuditRepository(ctx.db))


async def _require_space_admin(space_id: UUID, ctx: RequestContext) -> None:
    has_access = await ACL(ctx.db).check_space_role(
        user_id=ctx.user.uuid,
        space_id=space_id,
        min_role="admin",
    )
    if not has_access:
        raise SpaceAccessError


# ─── 管理员路由 ────────────────────────────────────────────────────────────────

@admin_router.get("/logs")
async def list_logs(
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[UUID] = Query(None),
    space_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(authorize("admin:audit:view")),
) -> ResponseModel:
    """管理员 - 审计日志列表（支持过滤）"""
    filters = ActivityLogFilter(
        space_id=space_id,
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        start_date=start_date,
        end_date=end_date,
    )
    items, total = await _service(ctx).search_logs(filters, limit=limit, offset=offset)
    return ResponseModel.success({
        "items": [x.model_dump(mode="json") for x in items],
        "total": total,
    })


@admin_router.get("/logs/{log_id}")
async def get_log(
    log_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:audit:view")),
) -> ResponseModel:
    """管理员 - 单条审计日志"""
    log = await _service(ctx).get_log(log_id)
    return ResponseModel.success(log.model_dump(mode="json") if log else None)


@admin_router.get("/users/{user_id}/logs")
async def list_user_logs(
    user_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(authorize("admin:audit:view")),
) -> ResponseModel:
    """管理员 - 用户审计时间线"""
    logs = await _service(ctx).get_user_logs(user_id, limit=limit, offset=offset)
    return ResponseModel.success([x.model_dump(mode="json") for x in logs])


@admin_router.get("/users/{user_id}/stats")
async def user_statistics(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    ctx: RequestContext = Depends(authorize("admin:audit:view")),
) -> ResponseModel:
    """管理员 - 用户操作统计"""
    stats = await _service(ctx).get_user_statistics(user_id, days=days)
    return ResponseModel.success(stats)


# ─── Space 隔离路由 ────────────────────────────────────────────────────────────

@space_router.get("/logs")
async def space_list_logs(
    space_id: UUID,
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(get_request_context),
) -> ResponseModel:
    """Space 管理员 - 查看本空间审计日志"""
    await _require_space_admin(space_id, ctx)
    filters = ActivityLogFilter(
        space_id=space_id,
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        start_date=start_date,
        end_date=end_date,
    )
    items, total = await _service(ctx).search_logs(filters, limit=limit, offset=offset)
    return ResponseModel.success({
        "items": [x.model_dump(mode="json") for x in items],
        "total": total,
    })


@space_router.get("/logs/{log_id}")
async def space_get_log(
    space_id: UUID,
    log_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> ResponseModel:
    """Space 管理员 - 查看本空间单条审计日志"""
    await _require_space_admin(space_id, ctx)
    log = await _service(ctx).get_log(log_id)
    if log and log.space_id != space_id:
        return ResponseModel.success(None)
    return ResponseModel.success(log.model_dump(mode="json") if log else None)


@space_router.get("/users/{user_id}/logs")
async def space_list_user_logs(
    space_id: UUID,
    user_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(get_request_context),
) -> ResponseModel:
    """Space 管理员 - 查看本空间某用户的审计时间线"""
    await _require_space_admin(space_id, ctx)
    filters = ActivityLogFilter(space_id=space_id, user_id=user_id)
    items, _ = await _service(ctx).search_logs(filters, limit=limit, offset=offset)
    return ResponseModel.success([x.model_dump(mode="json") for x in items])


@space_router.get("/users/{user_id}/stats")
async def space_user_statistics(
    space_id: UUID,
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    ctx: RequestContext = Depends(get_request_context),
) -> ResponseModel:
    """Space 管理员 - 查看本空间某用户的操作统计"""
    await _require_space_admin(space_id, ctx)
    stats = await _service(ctx).get_user_statistics_in_space(user_id, space_id, days=days)
    return ResponseModel.success(stats)


router.include_router(admin_router)
router.include_router(space_router)
