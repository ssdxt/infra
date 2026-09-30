"""存储后端抽象接口。

所有具体后端（本地 / S3）都实现这套接口；业务层与 `StorageService` 只依赖它。

Key 约定：统一虚拟路径，形如 `{space_id}/{kbase}/documents/source/{file}`。
后端内部决定如何映射到 bucket / object 或文件系统。
"""

from abc import ABC, abstractmethod
from typing import BinaryIO

from storage.types import ObjectStat


class StorageBackend(ABC):
    """统一存储后端接口。"""

    # ─── 写入 ────────────────────────────────────────────────────────

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str | None = None,
    ) -> ObjectStat:
        """写入对象，返回元信息。"""

    # ─── 读取 ────────────────────────────────────────────────────────

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """读取全部内容。"""

    @abstractmethod
    async def download_to(self, key: str, local_path: str) -> None:
        """下载到本地文件。"""

    # ─── 查询 / 删除 ─────────────────────────────────────────────────

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def stat(self, key: str) -> ObjectStat | None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    # ─── 预签名 URL ──────────────────────────────────────────────────

    @abstractmethod
    async def presign(self, key: str, ttl: int = 3600) -> str: ...

    # ─── 复制 / 移动 ─────────────────────────────────────────────────

    @abstractmethod
    async def copy(self, src_key: str, dst_key: str) -> None: ...

    async def move(self, src_key: str, dst_key: str) -> None:
        """默认实现：copy + delete。后端可覆盖以获得原子语义。"""
        await self.copy(src_key, dst_key)
        await self.delete(src_key)

    # ─── 命名空间（bucket / 根目录）初始化 ───────────────────────────

    @abstractmethod
    async def ensure_namespace(self, namespace: str) -> None:
        """确保一级命名空间（S3 bucket / 本地根目录）存在。"""

    @abstractmethod
    async def ensure_prefix(self, key: str) -> None:
        """在命名空间内预创建占位目录（key 以 `/` 结尾）。"""

    # ─── 健康检查 ────────────────────────────────────────────────────

    @abstractmethod
    async def health_check(self) -> None:
        """启动自检：连不通应抛异常。"""
