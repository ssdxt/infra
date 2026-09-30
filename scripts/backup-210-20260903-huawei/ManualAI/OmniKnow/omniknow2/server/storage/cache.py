"""MD5 → 本地缓存路径映射。

从原 `OSSService.get_or_download` 中抽出，保持后端无感知。
只给 `StorageService.get_or_fetch_source()` 使用。
"""

import os

from ext.redis_client import RedisClient
from utils.log import logger


class Md5PathCache:
    """基于 Redis 的 MD5 → 本地文件路径缓存。"""

    def __init__(self, redis: RedisClient | None = None):
        self.redis = redis or RedisClient()

    async def get(self, md5: str) -> str | None:
        cached = await self.redis.get_file_path(md5)
        if not cached:
            return None
        path = cached.decode("utf-8") if isinstance(cached, (bytes, bytearray)) else cached
        if os.path.isfile(path):
            logger.info(f"文件缓存命中: md5={md5}, local_path={path}")
            return path
        logger.info("文件缓存路径已过时")
        await self.redis.delete_file_path(md5)
        return None

    async def set(self, md5: str, local_path: str) -> None:
        await self.redis.set_file_path(md5, local_path)

    async def delete(self, md5: str) -> None:
        await self.redis.delete_file_path(md5)
