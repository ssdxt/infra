from celery.schedules import crontab
from datetime import timedelta

# Celery Beat 定时任务调度配置
# 注意：这里只使用任务的字符串名称引用，不要直接 import 任务函数，
# 否则会导致循环导入：ext.celery_app → backend.schedule → backend.tasks → ext.celery_app
beat_schedule = {
    # 清理临时文件：每天凌晨 3:00
    "cleanup-temp-files": {
        "task": "backend.tasks.cleanup_temp_files",
        "schedule": crontab(hour=3, minute=0),
    },
    # 清理 Redis 中过期的任务记录：每 6 小时
    "cleanup-expired-tasks": {
        "task": "backend.tasks.cleanup_expired_tasks",
        "schedule": timedelta(hours=6),
    },
    # 清理长时间 pending 的资源：每天凌晨 4:00
    "cleanup-stale-resources": {
        "task": "backend.tasks.cleanup_stale_resources",
        "schedule": crontab(hour=4, minute=0),
    },
    # 插入记忆：每 10 分钟
    "insert-memory": {
        "task": "backend.tasks.insert_memory",
        "schedule": timedelta(minutes=10),
    },
}
