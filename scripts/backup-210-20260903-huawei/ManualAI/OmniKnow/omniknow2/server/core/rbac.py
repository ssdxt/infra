from fastapi import Depends, Request, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


async def check_rbac(user, permission_code: str, redis: Redis, db: AsyncSession = None) -> bool:
    """
    基于 RBAC 的权限校验，支持缓存 miss 时自动从 DB 加载
    """
    if permission_code == "public":
        return True

    key = f"user_permissions:{user.uuid}"

    # 如果缓存不存在且有 db session，自动从 DB 加载
    exists = await redis.exists(key)
    if not exists and db is not None:
        from core.permission_cache import refresh_user_permissions
        await refresh_user_permissions(redis, user.uuid, db)

    is_superadmin = await redis.sismember(key, "superadmin")
    if is_superadmin:
        return True
    has_permission = await redis.sismember(key, permission_code)
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: 该用户没有权限执行此操作"
        )
    return True