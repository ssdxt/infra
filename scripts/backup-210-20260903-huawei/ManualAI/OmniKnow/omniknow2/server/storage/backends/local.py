"""本地文件系统后端。"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import BinaryIO

import aiofiles

from storage.backend import StorageBackend
from storage.types import ObjectStat
from utils.log import logger


class LocalBackend(StorageBackend):
    """把统一 key 直接映射到 `{base_path}/{key}`。

    `presign` 返回 `file://` 形式的 URI —— 中后台纯本地模式下由静态文件路由另行暴露，
    这里不强制绑定 HTTP 层。
    """

    def __init__(self, base_path: str, public_url_prefix: str | None = None):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.public_url_prefix = public_url_prefix  # 可选：例如 http://host/files

    # ─── 内部工具 ────────────────────────────────────────────────────

    def _abs(self, key: str) -> Path:
        # 防目录遍历：禁止 key 出现 `..`
        if ".." in Path(key).parts:
            raise ValueError(f"invalid key with '..': {key}")
        return self.base_path / key

    @staticmethod
    async def _ensure_parent(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    # ─── 写入 ────────────────────────────────────────────────────────

    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str | None = None,
    ) -> ObjectStat:
        path = self._abs(key)
        await self._ensure_parent(path)

        md5 = hashlib.md5()
        size = 0
        async with aiofiles.open(path, "wb") as f:
            if isinstance(data, (bytes, bytearray)):
                await f.write(data)
                md5.update(data)
                size = len(data)
            else:
                # 同步二进制流（如 UploadFile.file）
                while True:
                    chunk = data.read(1024 * 1024)
                    if not chunk:
                        break
                    await f.write(chunk)
                    md5.update(chunk)
                    size += len(chunk)

        return ObjectStat(
            key=key,
            size=size,
            etag=md5.hexdigest(),
            content_type=content_type,
            last_modified=path.stat().st_mtime,
        )

    # ─── 读取 ────────────────────────────────────────────────────────

    async def get(self, key: str) -> bytes:
        async with aiofiles.open(self._abs(key), "rb") as f:
            return await f.read()

    async def download_to(self, key: str, local_path: str) -> None:
        src = self._abs(key)
        dst = Path(local_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        # 本地 backend 下如果 src == dst，直接跳过
        if src.resolve() == dst.resolve():
            return
        shutil.copyfile(src, dst)

    # ─── 查询 / 删除 ─────────────────────────────────────────────────

    async def exists(self, key: str) -> bool:
        return self._abs(key).is_file()

    async def stat(self, key: str) -> ObjectStat | None:
        path = self._abs(key)
        if not path.is_file():
            return None
        st = path.stat()
        return ObjectStat(
            key=key,
            size=st.st_size,
            etag=None,
            content_type=None,
            last_modified=st.st_mtime,
        )

    async def delete(self, key: str) -> None:
        path = self._abs(key)
        try:
            if path.is_file():
                path.unlink()
        except Exception as e:
            logger.warning(f"本地文件删除失败: {path}, 原因: {e}")

    # ─── 预签名 ──────────────────────────────────────────────────────

    async def presign(self, key: str, ttl: int = 3600) -> str:
        if self.public_url_prefix:
            return f"{self.public_url_prefix.rstrip('/')}/{key.lstrip('/')}"
        return self._abs(key).as_uri()

    # ─── 复制 ────────────────────────────────────────────────────────

    async def copy(self, src_key: str, dst_key: str) -> None:
        src = self._abs(src_key)
        dst = self._abs(dst_key)
        await self._ensure_parent(dst)
        shutil.copyfile(src, dst)

    # ─── 命名空间 ────────────────────────────────────────────────────

    async def ensure_namespace(self, namespace: str) -> None:
        (self.base_path / namespace).mkdir(parents=True, exist_ok=True)

    async def ensure_prefix(self, key: str) -> None:
        self._abs(key).mkdir(parents=True, exist_ok=True)

    async def health_check(self) -> None:
        if not self.base_path.exists():
            raise RuntimeError(f"存储根目录不存在: {self.base_path}")
        if not os.access(self.base_path, os.W_OK):
            raise RuntimeError(f"存储根目录不可写: {self.base_path}")
