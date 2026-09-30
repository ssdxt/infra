from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from repository.role import RoleRepository
from repository.user import UserRepository


async def refresh_user_permissions(redis: Redis, user_id: UUID, db: AsyncSession) -> None:
    """重新从 DB 加载权限并写入 Redis 缓存"""
    key = f"user_permissions:{user_id}"
    await redis.delete(key)

    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)

    is_superadmin = await user_repo.is_superadmin(user_id)
    expire_seconds = settings.env.expire_time * 24 * 60 * 60

    if is_superadmin:
        await redis.sadd(key, "superadmin")
    else:
        permissions = await role_repo.get_user_permissions_from_db(user_id)
        if permissions:
            await redis.sadd(key, *permissions)

    await redis.expire(key, expire_seconds)


async def invalidate_user_permissions(redis: Redis, user_id: UUID) -> None:
    """清除用户权限缓存，强制下次请求时重新验证"""
    await redis.delete(f"user_permissions:{user_id}")


async def load_permissions_if_missing(redis: Redis, user_id: UUID, db: AsyncSession) -> None:
    """如果 Redis 中缓存不存在，自动从 DB 加载"""
    key = f"user_permissions:{user_id}"
    exists = await redis.exists(key)
    if not exists:
        await refresh_user_permissions(redis, user_id, db)
