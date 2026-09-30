from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Request

from audit.repository import AuditRepository
from db.session import async_session


@dataclass(frozen=True)
class AuditSpec:
    """声明式业务审计规范。

    用法：
        authorize("role:create", audit=AuditSpec(action="role_create", target_type="role"))
    """
    action: str
    target_type: Optional[str] = None
    target_param: Optional[str] = None  # path_params 中 target_id 的键；默认用 {target_type}_id
    space_param: str = "space_id"


def _parse_uuid(value) -> Optional[UUID]:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


async def write_audit(
    ctx,
    spec: AuditSpec,
    request: Request,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """由扩展后的 authorize() 在请求完成后调用。"""
    target_key = spec.target_param or (f"{spec.target_type}_id" if spec.target_type else None)
    target_id = _parse_uuid(request.path_params.get(target_key)) if target_key else None
    space_id = _parse_uuid(request.path_params.get(spec.space_param))

    detail = dict(getattr(request.state, "audit_detail", None) or {})
    # 允许 service 层通过 audit_detail 覆写 target_id（例如创建型接口，target_id 在响应体里）
    override_target = _parse_uuid(detail.pop("_target_id", None))
    if override_target:
        target_id = override_target

    if not success:
        detail["_success"] = False
        if error:
            detail["_error"] = error

    try:
        # 使用独立 session，避免主请求 session 被回滚时审计丢失
        async with async_session() as session:
            await AuditRepository(session).create_log_from_request(
                request=request,
                user_id=ctx.user.uuid if ctx.user else None,
                space_id=space_id,
                action=spec.action,
                target_type=spec.target_type,
                target_id=target_id,
                detail=detail or None,
            )
    except Exception:
        from utils.log import logger
        logger.exception("ActivityLog 写入失败 action=%s", spec.action)
