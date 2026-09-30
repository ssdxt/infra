import json
import time
import uuid
from dataclasses import dataclass, field

from core.config import settings
from core.acl.schema import ResourceStatus
from ext.celery_app import celery_app
from ext.redis_client import get_redis
from schemas.kbase import ParseOptions

_TASK_TTL = 86400  # 任务在 Redis 中的保留时长（秒）


@dataclass
class ParseTask:
    """
    文档解析任务 = 任务上下文 + 解析配置。

    任务上下文（必填）描述"解析谁"；
    解析配置（parse_config）描述"怎么解析"，直接引用 ParseOptions。

    新增解析参数只需在 ParseOptions 中声明，
    ParseTask 和 dispatch_parse_task 无需任何改动。

    用法示例：
        task = ParseTask(
            user_id=str(user.uuid),
            file_id=str(doc.uuid),
            md5=md5,
            file_path=local_path,
            space_id=str(space_id),
            kbase_id=str(kbase_id),
            kbase_name=kbase.name,
            collection_name=kbase.collection_name,
            chunk_source=chunk_source,
            parse_config=opts,  # ParseOptions 实例，可省略（使用默认值）
        )
        task_id = await dispatch_parse_task(task)
    """

    # --- 任务上下文（必填） ---
    user_id: str
    file_id: str
    file_name: str
    md5: str
    file_path: str
    source_oss_path: str
    space_id: str
    kbase_id: str
    kbase_name: str
    collection_name: str
    chunk_source: str

    # --- 任务标识（自动生成） ---
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # --- 解析配置（直接引用 ParseOptions，不再逐字段展开） ---
    parse_config: ParseOptions = field(default_factory=ParseOptions)


async def dispatch_parse_task(task: ParseTask) -> str:
    """
    将解析任务写入 Redis 并投递到 Celery 文档解析队列。

    任务数据在 Redis 中以 Hash 存储（key: task:{task_id}），TTL 24 小时。
    Celery worker 通过 task_id 从 Redis 读取 parse_config 后执行解析。

    parse_config JSON 包含任务上下文字段和 ParseOptions 的全部字段，
    新增解析参数只需修改 ParseOptions，此处自动透传。

    Args:
        task: ParseTask 实例

    Returns:
        task_id
    """
    redis = get_redis(settings.redis.task_db)
    try:
        # 任务上下文 + 解析配置合并为一个 dict，一次性 JSON 序列化
        config = {
            # "task_id": task.task_id,
            # "user_id": task.user_id,
            # "file_id": task.file_id,
            # "md5": task.md5,
            **task.parse_config.model_dump(),
        }
        await redis.hset(
            f"task:{task.task_id}",
            mapping={
                "id": task.task_id,
                "space_id": task.space_id,
                "kbase_id": task.kbase_id,
                "kbase_name": task.kbase_name,
                "collection_name": task.collection_name,
                "source_oss_path": task.source_oss_path,
                "user_id": task.user_id,
                "status": ResourceStatus.pending,
                "method": task.parse_config.method,
                "message": "正在队列",
                "file_id": task.file_id,
                "file_name": task.file_name,
                "file_path": task.file_path,
                "chunk_source": task.chunk_source,
                "md5": task.md5,
                "created_at": str(int(time.time())),
                "parse_config": json.dumps(config),
            },
        )
        await redis.expire(f"task:{task.task_id}", _TASK_TTL)
        celery_app.send_task(
            "backend.document_worker.parse_document",
            args=[task.task_id],
            queue="document_processing",
        )
        return task.task_id
    finally:
        await redis.aclose()