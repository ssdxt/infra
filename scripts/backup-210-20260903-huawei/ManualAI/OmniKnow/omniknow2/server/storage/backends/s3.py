"""S3 / RustFS / MinIO 对象存储后端。

迁移自原 `oss/rustfs.py`，实现 `StorageBackend` 接口。

命名空间映射：统一 key 的第一段为 **bucket**，剩余部分为 **object key**。
另对 `public/` 前缀做特判，允许把公共资源映射到独立 bucket。
"""

import hashlib
from typing import BinaryIO

import aioboto3
from botocore.config import Config

from storage.backend import StorageBackend
from storage.paths import split_namespace
from storage.types import ObjectStat


class S3Backend(StorageBackend):
    """基于 aioboto3 的 S3 兼容后端。

    `wan` 参数用于构造走公网地址的实例，只用于生成 presigned URL（原 RustFSClient
    `is_local=False` 的语义）。读写仍走内网实例。
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str = "eu-central-1",
    ):
        self.session = aioboto3.Session()
        self.client_kwargs = {
            "service_name": "s3",
            "endpoint_url": endpoint,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
            "config": Config(
                connect_timeout=5,
                read_timeout=20,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        }

    def _client(self):
        return self.session.client(**self.client_kwargs)

    # ─── 写入 ────────────────────────────────────────────────────────

    async def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str | None = None,
    ) -> ObjectStat:
        bucket, obj = split_namespace(key)
        # 计算 MD5 & size（同时保留 body）
        if isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        else:
            body = data.read() if hasattr(data, "read") else data
        md5 = hashlib.md5(body).hexdigest()
        size = len(body)

        async with self._client() as s3:
            await s3.put_object(
                Bucket=bucket,
                Key=obj,
                Body=body,
                ContentType=content_type or "application/octet-stream",
            )
        return ObjectStat(key=key, size=size, etag=md5, content_type=content_type)

    # ─── 读取 ────────────────────────────────────────────────────────

    async def get(self, key: str) -> bytes:
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            resp = await s3.get_object(Bucket=bucket, Key=obj)
            async with resp["Body"] as stream:
                return await stream.read()

    async def download_to(self, key: str, local_path: str) -> None:
        from pathlib import Path

        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            await s3.download_file(Bucket=bucket, Key=obj, Filename=local_path)

    # ─── 查询 / 删除 ─────────────────────────────────────────────────

    async def exists(self, key: str) -> bool:
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=bucket, Key=obj)
                return True
            except Exception:
                return False

    async def stat(self, key: str) -> ObjectStat | None:
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            try:
                resp = await s3.head_object(Bucket=bucket, Key=obj)
            except Exception:
                return None
        return ObjectStat(
            key=key,
            size=int(resp.get("ContentLength", 0)),
            etag=(resp.get("ETag") or "").strip('"') or None,
            content_type=resp.get("ContentType"),
            last_modified=(
                resp["LastModified"].timestamp() if resp.get("LastModified") else None
            ),
        )

    async def delete(self, key: str) -> None:
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            await s3.delete_object(Bucket=bucket, Key=obj)

    # ─── 预签名 ──────────────────────────────────────────────────────

    async def presign(self, key: str, ttl: int = 3600) -> str:
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": obj},
                ExpiresIn=ttl,
            )

    # ─── 复制 ────────────────────────────────────────────────────────

    async def copy(self, src_key: str, dst_key: str) -> None:
        src_bucket, src_obj = split_namespace(src_key)
        dst_bucket, dst_obj = split_namespace(dst_key)
        async with self._client() as s3:
            await s3.copy_object(
                Bucket=dst_bucket,
                Key=dst_obj,
                CopySource={"Bucket": src_bucket, "Key": src_obj},
            )

    # ─── 命名空间 ────────────────────────────────────────────────────

    async def ensure_namespace(self, namespace: str) -> None:
        """确保 bucket 存在（已存在时忽略）。"""
        async with self._client() as s3:
            try:
                await s3.create_bucket(Bucket=namespace)
                await s3.put_buckt_acl(Bucket=namespace, ACL="publoc-read")
            except Exception:
                pass

    async def ensure_prefix(self, key: str) -> None:
        """通过写入一个以 `/` 结尾的空对象占位。"""
        if not key.endswith("/"):
            key += "/"
        bucket, obj = split_namespace(key)
        async with self._client() as s3:
            await s3.put_object(Bucket=bucket, Key=obj)

    async def health_check(self) -> None:
        async with self._client() as s3:
            await s3.list_buckets()
