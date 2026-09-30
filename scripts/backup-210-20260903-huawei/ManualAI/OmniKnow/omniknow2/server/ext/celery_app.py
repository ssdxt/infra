import sys
from pathlib import Path

# 确保项目根目录（server/）在 sys.path 中，
# 使 Celery CLI 启动时能正确解析 core、backend 等模块。
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from celery import Celery
from celery.signals import worker_process_init

from core.config import settings


@worker_process_init.connect
def _setup_worker_path(**kwargs):
    """每个 ForkPoolWorker 子进程启动时，确保 sys.path 包含项目根目录。"""
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)


redis_host = settings.redis.host
redis_port = settings.redis.port
redis_password = settings.redis.password
redis_db = settings.redis.db
redis_task_db = settings.redis.task_db

redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_task_db}"

celery_app = Celery(
    'tasks',
    broker=redis_url,
)


# 导入定时任务调度配置
from backend.schedule import beat_schedule

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,

    # 可靠性相关
    task_acks_late=True,                 # 任务执行完再 ack，避免 worker 挂了任务丢失
    worker_prefetch_multiplier=1,        # 减少"抢任务"造成的不均衡
    task_reject_on_worker_lost=True,     # worker 意外退出时让任务回队列

    # RedBeat 调度器配置（使用 Redis 持久化定时任务状态）
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=redis_url,
    redbeat_key_prefix="redbeat:",

    # 定时任务调度表
    beat_schedule=beat_schedule,
)


# ── 显式导入任务模块，确保所有 @celery_app.task 被注册 ──
# 必须放在 celery_app 创建和配置之后，避免 include 静默失败的问题
try:
    import backend.tasks  # noqa: F401, E402
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"无法导入 backend.tasks，定时任务将不会被注册: {e}")

try:
    import backend.document_worker  # noqa: F401, E402
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"无法导入 backend.document_worker，文档解析任务将不会被注册: {e}")
