import asyncio
import re
import time
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from audit.access_repository import AccessLogRepository
from core.config import settings


# 跳过记录的路径前缀（文档、健康检查、审计读接口本身）
_SKIP_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/dev",
)

# 跳过记录的路径正则（审计查询接口，避免递归刷数据）
_SKIP_PATTERNS = (
    re.compile(r"^/api/v1/admin/audit(/|$)"),
    re.compile(r"^/api/v1/spaces/[^/]+/audit(/|$)"),
)

# 粗略从 path 里提取 UUID 形态的 space_id
_SPACE_ID_PATTERN = re.compile(
    r"/spaces/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def _should_skip(path: str) -> bool:
    if path.startswith(_SKIP_PREFIXES):
        return True
    return any(p.match(path) for p in _SKIP_PATTERNS)


def _extract_user_id(request: Request) -> Optional[UUID]:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    try:
        payload = jwt.decode(
            token,
            settings.env.secret_key,
            algorithms=[settings.env.algorithm],
        )
        uid = payload.get("uuid")
        return UUID(uid) if uid else None
    except (JWTError, ValueError, TypeError):
        return None


def _extract_space_id(path: str) -> Optional[UUID]:
    m = _SPACE_ID_PATTERN.search(path)
    if not m:
        return None
    try:
        return UUID(m.group(1))
    except ValueError:
        return None


def _client_ip(request: Request) -> Optional[str]:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


class AccessLogMiddleware(BaseHTTPMiddleware):
    """所有认证请求的粗粒度访问日志（异步写入，不阻塞响应）"""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if _should_skip(path):
            return await call_next(request)

        start = time.perf_counter()
        status_code: Optional[int] = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            asyncio.create_task(AccessLogRepository.create(
                user_id=_extract_user_id(request),
                space_id=_extract_space_id(path),
                method=request.method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                ip_address=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            ))
