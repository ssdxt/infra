import os
import sys
import time
import traceback
from pathlib import Path

# 确保 Worker 子进程（ForkPoolWorker）也能找到项目模块
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import redis

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from ext.celery_app import celery_app
from core.config import settings
from utils.log import logger


# ──────────────────────────────────────────────
# 同步数据库连接（Celery worker 运行在同步上下文）
# ──────────────────────────────────────────────
def _build_sync_db_url() -> str:
    cfg = settings.database
    if cfg.type == "pg":
        return f"postgresql+psycopg2://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}"
    elif cfg.type == "mysql":
        return f"mysql+pymysql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}"
    raise ValueError(f"不支持的数据库类型: {cfg.type}")


def _get_sync_session():
    engine = create_engine(_build_sync_db_url(), pool_pre_ping=True, pool_recycle=3600)
    return sessionmaker(bind=engine)()


# ──────────────────────────────────────────────
# Redis 客户端（同步）
# ──────────────────────────────────────────────
def _get_redis_client(db: int = 1) -> redis.Redis:
    return redis.Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        db=db,
        decode_responses=True,
    )


# ──────────────────────────────────────────────
# 分布式锁，防止任务重复执行
# ──────────────────────────────────────────────
def _acquire_lock(r: redis.Redis, lock_name: str, timeout: int = 600) -> bool:
    """尝试获取分布式锁，timeout 秒后自动释放"""
    return bool(r.set(f"backend:lock:{lock_name}", "1", nx=True, ex=timeout))


def _release_lock(r: redis.Redis, lock_name: str):
    r.delete(f"backend:lock:{lock_name}")


# ══════════════════════════════════════════════
# 定时任务定义
# ══════════════════════════════════════════════

@celery_app.task(name="backend.tasks.cleanup_temp_files", bind=True, max_retries=0)
def cleanup_temp_files(self):
    """
    清理临时文件目录中超过 24 小时的文件。
    目录路径来自 settings.parser.file_path。
    """
    r = _get_redis_client()
    if not _acquire_lock(r, "cleanup_temp_files"):
        logger.info("cleanup_temp_files: 另一个实例正在执行，跳过")
        return

    try:
        temp_dir = settings.parser.file_path
        if not os.path.isdir(temp_dir):
            logger.warning(f"临时文件目录不存在: {temp_dir}")
            return

        now = time.time()
        threshold = 24 * 3600  # 24 小时
        removed_count = 0

        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    if now - os.path.getmtime(filepath) > threshold:
                        os.remove(filepath)
                        removed_count += 1
                except OSError as e:
                    logger.warning(f"删除文件失败 {filepath}: {e}")

            # 删除空目录（不删除根目录）
            for name in dirs:
                dirpath = os.path.join(root, name)
                try:
                    if not os.listdir(dirpath):
                        os.rmdir(dirpath)
                except OSError:
                    pass

        logger.info(f"cleanup_temp_files: 清理完成，删除 {removed_count} 个过期文件")
    finally:
        _release_lock(r, "cleanup_temp_files")


@celery_app.task(name="backend.tasks.cleanup_expired_tasks", bind=True, max_retries=0)
def cleanup_expired_tasks(self):
    """
    清理 Redis 中已过期的任务记录。
    扫描 task:* 键，删除超过 48 小时未更新的记录。
    """
    r = _get_redis_client()
    if not _acquire_lock(r, "cleanup_expired_tasks"):
        logger.info("cleanup_expired_tasks: 另一个实例正在执行，跳过")
        return

    try:
        now = time.time()
        threshold = 48 * 3600  # 48 小时
        removed_count = 0
        cursor = 0

        while True:
            cursor, keys = r.scan(cursor, match="task:*", count=100)
            for key in keys:
                try:
                    created_at = r.hget(key, "created_at")
                    if created_at and now - float(created_at) > threshold:
                        r.delete(key)
                        removed_count += 1
                except (ValueError, TypeError):
                    # created_at 字段格式不正确，跳过
                    pass
            if cursor == 0:
                break

        logger.info(f"cleanup_expired_tasks: 清理完成，删除 {removed_count} 条过期任务记录")
    finally:
        _release_lock(r, "cleanup_expired_tasks")


@celery_app.task(name="backend.tasks.cleanup_stale_resources", bind=True, max_retries=0)
def cleanup_stale_resources(self):
    """
    将长时间处于 pending 状态的资源标记为 failed。
    超过 24 小时仍为 pending 的资源视为异常。
    """
    from db.models.rag import Resource
    from core.acl.schema import ResourceStatus

    r = _get_redis_client()
    if not _acquire_lock(r, "cleanup_stale_resources"):
        logger.info("cleanup_stale_resources: 另一个实例正在执行，跳过")
        return

    session = None
    try:
        session = _get_sync_session()

        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(hours=24)

        result = session.execute(
            update(Resource)
            .where(Resource.status == ResourceStatus.pending)
            .where(Resource.created_at < cutoff)
            .values(status=ResourceStatus.failed)
        )
        session.commit()

        updated_count = result.rowcount
        logger.info(f"cleanup_stale_resources: 标记 {updated_count} 个过期 pending 资源为 failed")
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"cleanup_stale_resources 执行失败: {e}")
        raise
    finally:
        if session:
            session.close()
        _release_lock(r, "cleanup_stale_resources")


@celery_app.task(name="backend.tasks.insert_memory", bind=True, max_retries=0)
def insert_memory(self):
    """
    插入记忆的定时任务示例。
    该任务定时扫描聊天列表，将未插入向量库的聊天记录数据插入向量库。
    """
    from db.models.rag import Conversation, ChatMessage
    import httpx

    logger.info("insert_memory: 定时任务开始执行，扫描未插入向量库的消息")
    r = _get_redis_client()
    if not _acquire_lock(r, "insert_memory"):
        logger.info("insert_memory: 另一个实例正在执行，跳过")
        return

    session = None
    success = 0
    failed = 0
    try:
        session = _get_sync_session()

        message_to_insert = session.query(ChatMessage, Conversation.user_id).join(
            Conversation, ChatMessage.conversation_id == Conversation.uuid
        ).filter(
            ChatMessage.is_vectorized.is_(False),
            Conversation.status == "active"
        ).all()

        logger.info(f"insert_memory: 找到 {len(message_to_insert)} 条未插入向量库的消息")

        # 按 conversation_id 分组
        from collections import defaultdict
        groups = defaultdict(list)
        user_id_map = {}
        for msg, user_id in message_to_insert:
            groups[msg.conversation_id].append(msg)
            user_id_map[msg.conversation_id] = user_id

        logger.info(f"insert_memory: 共 {len(groups)} 个会话需要插入")

        # 使用 httpx.Client 复用 TCP 连接，避免每次请求都新建/销毁连接
        # 导致 socket 处于 TIME_WAIT 状态，后续请求超时
        with httpx.Client(timeout=30) as client:
            for conversation_id, msgs in groups.items():
                user_id = user_id_map[conversation_id]
                body = {
                    "messages": [{"role": msg.role, "content": msg.text} for msg in msgs],
                    "thread_id": str(conversation_id),
                    "update_time": msgs[-1].timestamp,
                    "user_id": str(user_id),
                    "collection_name": "long_memory"
                }
                try:
                    res = client.post(f"{settings.parser.api_url}/memory_insert", json=body)
                except Exception as e:
                    failed += len(msgs)
                    logger.error(f"会话 {conversation_id} 插入向量库时发生异常: {e}")
                    continue

        session.commit()
        logger.info(f"insert_memory: 定时任务执行完成，成功插入 {success} 条消息，失败 {failed} 条")
    except Exception as e:
        traceback.print_exc()
        if session:
            session.rollback()
        logger.error(f"insert_memory 执行失败: {e}，成功插入 {success} 条消息，失败 {failed} 条")
    finally:
        if session:
            session.close()
        _release_lock(r, "insert_memory")