"""存储层通用 DTO。"""

from dataclasses import dataclass


@dataclass
class ObjectStat:
    """对象元信息。"""

    key: str
    size: int
    etag: str | None = None
    content_type: str | None = None
    last_modified: float | None = None


@dataclass
class SavedFile:
    """保存源文件后的完整信息。

    替代原 `(local_path, md5)` tuple，把 key / size / content_type 一并带出。
    """

    key: str                    # 统一虚拟路径（含 space_id 前缀）
    local_path: str             # 本地暂存路径（若有）
    md5: str
    size: int
    content_type: str | None = None
