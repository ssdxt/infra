import json

from redis.asyncio import Redis
from redis.exceptions import ConnectionError
from redis.exceptions import TimeoutError

from core.config import settings
from schemas.task import TaskResponse, Task
from utils import logger


def get_redis(db: int | None = None, decode: bool | None = False) -> Redis:
    """获取 Redis 客户端实例"""
    try:
        redis = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password,
            db=db if db else settings.redis.db,
            decode_responses=decode,
            socket_timeout=5,
        )
        return redis
    except ConnectionError as e:
        logger.error(f"Redis获取连接时出现错误: {e}")
        raise ConnectionError(f"内部组件出现网络异常， 请稍后重试")
    except TimeoutError as e:
        logger.error(f"Redis连接超时: {e}")
        raise TimeoutError(f"内部组件连接超时， 请稍后重试")


class RedisClient:
    def __init__(self, decode: bool = False):
        self.host = settings.redis.host
        self.port = settings.redis.port
        self.password = settings.redis.password
        self.db = settings.redis.db
        self.task_db = settings.redis.task_db
        self.decode = decode

    def _get_redis_client(self, task_queue: bool = False) -> Redis:
        """获取 Redis 客户端实例"""
        try:
            redis = Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.task_db if task_queue else self.db,
                decode_responses=self.decode
            )
            return redis
        except ConnectionError as e:
            logger.error(f"Redis获取连接时出现错误: {e}")
            raise ConnectionError(f"内部组件出现网络异常， 请稍后重试")

    async def set(self, key: str, value: str, ex: int = 0) -> None:
        """设置键值对"""
        redis = self._get_redis_client()
        await redis.set(key, value, ex=ex)
        await redis.close()

    async def get(self, key: str):
        """获取键值对"""
        redis = self._get_redis_client()
        value = await redis.get(key)
        await redis.close()
        return value

    async def hset(self, name: str, key: str, value: str) -> None:
        """设置哈希表键值对"""
        redis = self._get_redis_client()
        await redis.hset(name, key, value)
        await redis.close()

    async def hset_mapping(self, name: str, mapping: dict) -> None:
        """设置哈希表多个键值对"""
        redis = self._get_redis_client(True)
        await redis.hset(name, mapping=mapping)
        await redis.close()

    async def hget(self, name: str, key: str):
        """获取哈希表键值对"""
        redis = self._get_redis_client(True)
        value = await redis.hget(name, key)
        await redis.close()
        return value

    async def hgetall(self, name: str):
        """获取哈希表所有键值对"""
        redis = self._get_redis_client(True)
        value = await redis.hgetall(name)
        await redis.close()
        return value

    async def get_task_result(self, task_id: str):
        """获取任务信息"""
        redis = self._get_redis_client(True)
        try:
            task_data = await redis.hgetall(f"task:{task_id}")
            if not task_data:
                return None
            return TaskResponse(**{k.decode(): v.decode() for k, v in task_data.items()})
        finally:
            await redis.close()

    async def get_task(self, task_id: str) -> Task | None:
        """从 Redis 获取完整任务信息，返回 Task 模型"""
        redis = self._get_redis_client(task_queue=True)
        task_data = await redis.hgetall(f"task:{task_id}")
        await redis.close()
        if not task_data:
            return None
        return Task(**{k.decode(): v.decode() for k, v in task_data.items()})

    async def set_task_status(self, task_id: str, status: str | None, message: str | None) -> None:
        """设置任务状态"""
        redis = self._get_redis_client(task_queue=True)
        if status:
            await redis.hset(f"task:{task_id}", "status", status)
        if message:
            await redis.hset(f"task:{task_id}", "message", message)
        await redis.close()

    async def return_task_result(self, task_id: str, result: dict) -> None:
        """返回任务结果"""
        redis = self._get_redis_client(task_queue=True)
        await redis.hset(f"task:{task_id}", "result", json.dumps(result))
        await redis.close()

    async def set_file_path(self, file_key: str, file_path: str) -> None:
        """设置任务文件路径"""
        redis = self._get_redis_client()
        await redis.set(f"file:{file_key}", file_path, ex=7200)
        await redis.close()

    async def get_file_path(self, file_key: str) -> str | bytes |None:
        """获取任务文件路径"""
        redis = self._get_redis_client()
        file_path = await redis.get(f"file:{file_key}")
        await redis.close()
        return file_path

    async def delete_file_path(self, file_key: str) -> None:
        """删除任务文件路径"""
        redis = self._get_redis_client()
        await redis.delete(f"file:{file_key}")
        await redis.close()

