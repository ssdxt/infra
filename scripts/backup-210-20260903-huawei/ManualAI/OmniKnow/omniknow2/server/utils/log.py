import sys

from loguru import logger


logger.remove()

log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

logger.add(
    sys.stderr,
   level="INFO",
   format=log_format,
   colorize=True
)

logger.add(
    "logs/app.log",
    level="INFO",
    format=log_format,
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    enqueue=True,  # 设置为 True 使日志记录在多进程环境下安全
    backtrace=True, # 发生异常时，记录完整的堆栈回溯
    diagnose=True   # 发生异常时，记录更详细的诊断信息
)