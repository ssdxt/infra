import os
import json

from dotenv import load_dotenv

from redis.asyncio import Redis
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

load_dotenv()


class Task(BaseModel):
    """
    Worker 侧任务模型。

    Redis Hash 结构：
      - 顶层字段：id / user_id / status / message / file_id / md5 / created_at
      - parse_config：JSON 字符串，包含 ParseTask 的全部配置字段

    `expand_parse_config` validator 会自动将 parse_config 展开合并到模型，
    因此新增配置字段时只需在 server 侧的 ParseTask dataclass 中声明，
    worker 侧无需修改 get_task() 解析逻辑——新字段可通过 task.<field> 直接访问。
    """

    model_config = ConfigDict(extra="allow")

    # 任务元数据（Redis Hash 顶层字段）
    id: str
    user_id: str = ""
    status: str
    created_at: int
    file_id: str
    md5: str

    # 解析配置字段（由 parse_config 展开，与 ParseTask 字段名保持一致）
    file_path: str = ""
    space_id: str = ""
    kbase_id: str = ""
    kbase_name: str = ""
    collection_name: str = ""
    img_collection_name: str = "images2"
    summary_collection_name: str = "chapter_summary"
    method: str = "smart"   # 解析模式（normal / smart）
    max_chunk_size: int = 1024
    chunk_overlap: int = 0
    delimiters: list[str] = []
    summary: bool = False
    backend: str = "hybrid-auto-engine"  # hybrid-auto-engine 或者 pipeline
    table: bool = True
    parent_titles: bool = True
    title_correction: bool = True
    start_page: int = 0
    end_page: int = 99999
    
    

    # 任务运行时结果
    message: str | None = None
    chunks: list[dict] | None = None
    chunk_count: int | None = None
    result: dict | str | None = None

    @model_validator(mode="before")
    @classmethod
    def expand_parse_config(cls, data: dict) -> dict:
        """将 parse_config JSON 自动展开合并到顶层，新增配置字段无需修改此处。"""
        if not isinstance(data, dict) or "parse_config" not in data:
            return data
        raw = data.pop("parse_config")
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()
        if isinstance(raw, str):
            config = json.loads(raw)
        else:
            config = raw
        # 顶层字段优先，不被 parse_config 内容覆盖
        for k, v in config.items():
            if k not in data:
                data[k] = v
        return data

    @field_validator("delimiters", mode="before")
    @classmethod
    def parse_delimiters(cls, v):
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            return list(v)
        if isinstance(v, (bytes, bytearray)):
            v = v.decode()
        if isinstance(v, str):
            return json.loads(v)
        return v

class RedisClint:
    def __init__(self) -> None:
        self.redis_host = os.getenv("REDIS_HOST")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 1))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        
    def _get_redis_client(self) -> Redis:
        """获取 Redis 客户端（同步创建客户端实例，方法可在异步上下文中使用返回的 client）。"""

        return Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            password=self.redis_password,
        )
    
    async def get_task(self, task_id: str) -> Task | None:
        """获取任务信息"""
        redis = self._get_redis_client()
        task_data = await redis.hgetall(f"task:{task_id}")
        if not task_data:
            return None
        await redis.close()
        return Task(**{k.decode(): v.decode() for k, v in task_data.items()})
    
    async def set_task_status(self, task_id: str, status: str | None, message: str | None) -> None:
        """设置任务状态"""
        redis = self._get_redis_client()
        if status:
            await redis.hset(f"task:{task_id}", "status", status)
        if message:
            await redis.hset(f"task:{task_id}", "message", message)
        await redis.close()

    async def return_task_result(self, task_id: str, result: dict) -> None:
        """返回任务结果"""
        redis = self._get_redis_client()
        await redis.hset(f"task:{task_id}", "result", json.dumps(result))
        await redis.close()

    

    