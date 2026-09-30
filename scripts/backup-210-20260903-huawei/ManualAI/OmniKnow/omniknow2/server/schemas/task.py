from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator, Field
import json


class TaskResponse(BaseModel):
    id: str
    file_id: str
    space_id: str
    kbase_id: str
    file_name: str
    source_oss_path: str
    kbase_name: str
    chunk_count: int = 1024
    collection_name: str
    # img_collection_name: str = "images2"
    # sum_collection_name: str = "chapter_summary"
    parser_config: dict | None = None
    method: str | None = "normal"
    result: dict = {}
    status: str

    @field_validator("result", mode="before")
    @classmethod
    def parse_result(cls, v):
        if not v:
            return {}
        return json.loads(v) if isinstance(v, str) else v


class TaskProgressResponse(BaseModel):
    task_id : UUID
    doc_id: UUID
    doc_name: str | None
    status: str
    message: str | None = None
    metadata: dict | None


SkipConvertExt = [".xlsx", ".pdf"]


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    converted = "converted"
    parsed = "parsed"
    vectorized = "vectorized"
    completed = "completed"
    failed = "failed"


class Task(BaseModel):
    """
    Worker 侧任务模型。

    Redis Hash 结构：
      - 顶层字段：id / user_id / status / message / file_id / md5 / created_at
      - parse_config：JSON 字符串，包含 ParseTask 的全部配置字段

    `expand_parse_config` validator 会自动将 parse_config 展开合并到模型，
    因此新增配置字段时只需在 ParseTask dataclass 中声明，
    worker 侧无需修改 get_task() 解析逻辑——新字段可通过 task.<field> 直接访问。
    """

    model_config = ConfigDict(extra="allow")

    # 任务元数据（Redis Hash 顶层字段）
    id: str
    user_id: str = ""
    status: str
    created_at: int
    file_id: str
    file_name: str | None = None
    md5: str

    # 解析配置字段（由 parse_config 展开，与 ParseTask 字段名保持一致）
    file_path: str = ""
    space_id: str = ""
    kbase_id: str = ""
    kbase_name: str = ""
    source_oss_path: str = ""
    collection_name: str = ""
    img_collection_name: str = "images2"
    summary_collection_name: str = "chapter_summary"
    method: str = "smart"
    max_chunk_size: int = 1024
    chunk_overlap: int = 0
    delimiters: list[str] = []
    summary: bool = False
    backend: str = "hybrid-auto-engine"
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


class TaskStatusQuerySchema(BaseModel):
    task_ids: list[UUID] = Field(..., description="文件ID列表")


ALLOWED_EXTENSIONS = ["txt", "pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv", "json", "jsonl", "md", "markdown"]
