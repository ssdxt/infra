"""统一存储服务门面。

所有业务层文件相关的能力（上传 / 下载 / 删除 / 预签名 / 元信息）都通过本模块完成。
业务代码禁止直接 import `storage.backends.*` 或 `aioboto3` / `aiofiles`。

设计要点：
- `backend`    : 持久化后端（S3 / Local），由配置决定。
- `presign_backend` : 专用于生成外链的后端（S3 场景下走 wan 地址）。
- `scratch`    : 本地暂存后端（`LocalBackend`），用于解析 worker 的本地输入/输出。
- `cache`      : 可选 MD5 → 本地路径缓存（Redis）。
"""

import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from storage import paths
from storage.backend import StorageBackend
from storage.backends.local import LocalBackend
from storage.cache import Md5PathCache
from storage.types import ObjectStat, SavedFile
from utils.log import logger


class StorageService:
    def __init__(
        self,
        backend: StorageBackend,
        presign_backend: StorageBackend | None = None,
        scratch: LocalBackend | None = None,
        cache: Md5PathCache | None = None,
        public_url_base: str | None = None,
    ):
        self.backend = backend
        self.presign_backend = presign_backend or backend
        self.scratch = scratch
        self.cache = cache
        # 用于拼接不带签名的直链 URL（保留原 OSSService.wan_url 的语义）
        self.public_url_base = public_url_base.rstrip("/") if public_url_base else None

    # ─── Key 规范化 ──────────────────────────────────────────────────

    @staticmethod
    def _as_key(space_id: UUID | str, path: str) -> str:
        """把「DB 里存的 bucket 相对路径」补全成统一 key（含 space_id 前缀）。

        兼容两种输入：
          - `{space_id}/...`  / `public/...` → 原样返回
          - `kbase/documents/source/file`   → 补上 space_id 前缀
        """
        prefix = f"{space_id}/"
        if path.startswith(prefix) or path.startswith("public/"):
            return path
        return f"{prefix}{path.lstrip('/')}"

    # ─── 上传 / 保存 ─────────────────────────────────────────────────

    async def save_source(
        self,
        file: UploadFile,
        space_id: UUID,
        kbase_name: str,
    ) -> SavedFile:
        """上传源文件：本地暂存 + 持久化后端 + MD5 缓存。

        返回的 `SavedFile.key` 里存的是 **不含 space_id 前缀** 的路径，
        与现 `resource.path` 字段的语义一致，方便业务层直接落库。
        """
        body, content_type = await self._read_upload(file)
        key = paths.source_key(space_id, kbase_name, file.filename)
        saved = await self._persist(
            space_id, key, body, content_type, scratch=True, cache=True
        )
        logger.info(
            f"文件 {file.filename} 已保存至本地并上传存储（key: {key}，MD5: {saved.md5}）"
        )
        return saved

    async def save_source_bytes(
        self,
        content_bytes: bytes,
        space_id: UUID,
        kbase_name: str,
        file_name: str,
        content_type: str = "application/octet-stream",
    ) -> SavedFile:
        """从字节流（如 Markdown）保存源文件。"""
        key = paths.source_key(space_id, kbase_name, file_name)
        saved = await self._persist(
            space_id, key, content_bytes, content_type, scratch=True, cache=True
        )
        logger.info(
            f"内容文件 {file_name} 已写入本地并上传存储（key: {key}，MD5: {saved.md5}）"
        )
        return saved

    async def save_processed(
        self, local_path: str, space_id: UUID, kbase_name: str
    ) -> str | bool:
        """解析 worker 产出的处理后文件上传到持久后端。

        返回 `"{kbase}/documents/processed/{file}"` 形态的相对 key（保留原
        `upload_processed_file` 的形态），便于直接落 DB。
        """
        if not local_path:
            return True
        p = Path(local_path)
        if not p.is_file():
            logger.error(f"文件不存在: {local_path}")
            return False
        key = paths.processed_key(space_id, kbase_name, p.name)
        await self.backend.put(key, p.read_bytes())
        logger.info(f"文件上传至存储成功: {key}")
        return key

    async def save_media(
        self,
        space_id: UUID | str,
        kbase_name: str,
        local_media_path: str,
    ) -> str:
        """上传 chunk 媒体文件，返回可供外部访问的 URL（直链）。"""
        p = Path(local_media_path)
        key = paths.media_key(space_id, kbase_name, p.name)
        await self.backend.put(key, p.read_bytes())
        return await self.public_url(space_id, self._strip_namespace(space_id, key))

    async def save_space_image(
        self,
        space_id: UUID,
        file: UploadFile,
        filename_stem: str,
        ext: str,
        ttl: int = 60 * 60 * 24,
    ) -> dict:
        """上传空间内图片，返回 `{url, path, expires_in}`。"""
        await self.ensure_space_bucket(space_id)
        body, content_type = await self._read_upload(file)
        key = paths.space_image_key(space_id, filename_stem, ext)
        await self.backend.put(key, body, content_type)
        return await self._signed_url_dict(space_id, key, ttl)

    async def save_space_logo(
        self, space_id: UUID, file: UploadFile, ttl: int = 3600
    ) -> dict:
        """上传空间 logo，返回 `{url, path, expires_in}`（默认 1h TTL）。"""
        await self.ensure_space_bucket(space_id)
        body, content_type = await self._read_upload(file)
        key = paths.space_logo_key(space_id, file.filename)
        await self.backend.put(key, body, content_type)
        return await self._signed_url_dict(space_id, key, ttl)

    async def put_bytes(
        self,
        space_id: UUID | str,
        relative_path: str,
        body: bytes,
        content_type: str | None = None,
    ) -> str:
        """通用裸上传：业务层自己决定 key，不走 scratch / cache。

        `relative_path` 与 `read_bytes` / `presign` 一致：可传不带 space_id
        前缀的相对路径，也可直接传含前缀的完整 key（含 `public/...`）。
        返回 DB 里落库用的相对 key（去掉 space_id 前缀）。
        """
        key = self._as_key(space_id, relative_path)
        await self.backend.put(key, body, content_type)
        return self._strip_namespace(space_id, key)

    # ─── 读取 ────────────────────────────────────────────────────────

    async def get_or_fetch_source(
        self,
        md5: str,
        relative_path: str,
        space_id: UUID,
        kbase_name: str,
        file_name: str,
    ) -> tuple[str, str]:
        """按 MD5 命中本地缓存，缺失时从持久后端下载到本地暂存区。"""
        key = self._as_key(space_id, relative_path)

        if self.cache:
            cached = await self.cache.get(md5)
            if cached:
                return cached, key

        # 持久后端下载到本地暂存路径

        local_path = self._scratch_abs(paths.source_key(space_id, kbase_name, file_name))
        local_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"文件缓存缺失，从存储下载: md5={md5}, key={key}")
        await self.backend.download_to(key, str(local_path))
        if self.cache:
            await self.cache.set(md5, str(local_path))
        return str(local_path), str(key)

    async def read_bytes(self, space_id: UUID, relative_path: str) -> bytes:
        return await self.backend.get(self._as_key(space_id, relative_path))

    # ─── 预签名 / 直链 ───────────────────────────────────────────────

    async def presign(
        self, space_id: UUID, relative_path: str, ttl: int = 3600
    ) -> str:
        return await self.presign_backend.presign(
            self._as_key(space_id, relative_path), ttl=ttl
        )

    async def public_url(self, space_id: UUID | str, relative_path: str) -> str:
        """构造不带签名的直链 URL（原 `OSSService.wan_url`）。

        仅在 `public_url_base` 有配置时才返回拼接结果，否则退化为 key 字符串。
        """
        rel = relative_path.lstrip("/")
        key = rel if (rel.startswith("public/") or rel.startswith(str(space_id))) else f"{space_id}/{rel}"
        return f"{self.public_url_base}/{key}" if self.public_url_base else key

    async def stat(self, space_id: UUID, relative_path: str) -> ObjectStat | None:
        return await self.backend.stat(self._as_key(space_id, relative_path))

    # ─── 删除 / 移动 / 复制 ──────────────────────────────────────────

    async def delete_resource_files(
        self,
        space_id: UUID,
        source_path: str | None,
        processed_path: str | None,
    ) -> None:
        """幂等清理资源相关的 source + processed 文件。"""
        for rel in (source_path, processed_path):
            if not rel or rel == "1":
                continue
            try:
                await self.backend.delete(self._as_key(space_id, rel))
            except Exception as e:
                logger.warning(f"删除文件失败: space={space_id}, path={rel}, err={e}")

    async def delete(self, space_id: UUID, relative_path: str) -> None:
        await self.backend.delete(self._as_key(space_id, relative_path))

    async def copy(
        self,
        space_id: UUID,
        src_rel: str,
        dst_rel: str,
    ) -> None:
        await self.backend.copy(
            self._as_key(space_id, src_rel), self._as_key(space_id, dst_rel)
        )

    async def move(
        self,
        space_id: UUID,
        src_rel: str,
        dst_rel: str,
    ) -> None:
        await self.backend.move(
            self._as_key(space_id, src_rel), self._as_key(space_id, dst_rel)
        )

    # ─── 命名空间 / 初始化 ───────────────────────────────────────────

    async def init_kbase_bucket(self, space_id: UUID | str, kbase_name: str) -> None:
        """初始化知识库存储结构：确保 space bucket + 占位目录。"""
        await self.backend.ensure_namespace(str(space_id))
        for key in paths.kbase_init_keys(space_id, kbase_name):
            try:
                await self.backend.ensure_prefix(key)
            except Exception as e:
                logger.warning(f"创建占位目录失败: {key}, {e}")

    async def ensure_space_bucket(self, space_id: UUID | str) -> None:
        """创建空间对应的命名空间（替代原 `RustFSClient.create_bucket`）。"""
        await self.backend.ensure_namespace(str(space_id))

    async def health_check(self) -> None:
        await self.backend.health_check()

    # ─── 本地暂存文件操作（供 task cleanup 等用） ────────────────────

    def local_exists(self, path: str | Path) -> bool:
        return Path(str(path)).is_file()

    async def delete_local(self, path: str | Path | None) -> None:
        """删除本地暂存文件，路径为空 / 不存在时静默。"""
        if not path:
            return
        try:
            p = Path(str(path))
            if p.exists():
                p.unlink()
                logger.info(f"本地文件已删除: {p}")
        except Exception as e:
            logger.warning(f"删除本地文件失败: {path}, 原因: {e}")

    # ─── 内部原语：输入适配 / 持久化 / URL 构造 ──────────────────────

    @staticmethod
    async def _read_upload(file: UploadFile) -> tuple[bytes, str | None]:
        """统一从 UploadFile 取出全量字节 + content_type，并保持流可重读。"""
        await file.seek(0)
        body = await file.read()
        await file.seek(0)
        return body, file.content_type

    async def _persist(
        self,
        space_id: UUID | str,
        key: str,
        body: bytes,
        content_type: str | None = None,
        *,
        scratch: bool = False,
        cache: bool = False,
    ) -> SavedFile:
        """统一上传：可选本地暂存 + 持久化后端 + 可选 MD5 缓存，返回 SavedFile。"""
        local_path = ""
        if scratch and self.scratch:
            await self.scratch.put(key, body, content_type)
            local_path = str(self._scratch_abs(key))

        await self.backend.put(key, body, content_type)

        md5 = _md5_hex(body)
        if cache and self.cache and local_path:
            await self.cache.set(md5, local_path)

        return SavedFile(
            key=self._strip_namespace(space_id, key),
            local_path=local_path,
            md5=md5,
            size=len(body),
            content_type=content_type,
        )

    async def _signed_url_dict(
        self, space_id: UUID | str, key: str, ttl: int
    ) -> dict:
        """构造 `{url, path, expires_in}` 三元组：预签名 URL + 直链 path。"""
        url = await self.presign_backend.presign(key, ttl=ttl)
        path = await self.public_url(space_id, self._strip_namespace(space_id, key))
        return {"url": url, "path": path, "expires_in": ttl}

    # ─── 内部工具 ────────────────────────────────────────────────────

    @staticmethod
    def _strip_namespace(space_id: UUID | str, key: str) -> str:
        """把 key 的 space_id 前缀去掉，得到 DB 里存的 bucket 相对路径。"""
        prefix = f"{space_id}/"
        return key[len(prefix):] if key.startswith(prefix) else key

    def _scratch_abs(self, key: str) -> Path:
        """把统一 key 映射到本地暂存路径。"""
        if self.scratch is None:
            raise RuntimeError("StorageService 未配置本地暂存（scratch）")
        return self.scratch._abs(key)


def _md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
