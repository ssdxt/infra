import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()


redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_db = os.getenv("REDIS_DB")
redis_password = os.getenv("REDIS_PASSWORD")


app = Celery(
    "worker",
    broker=f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}",
    backend=f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}",
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)
