"""存储路径规则（纯函数）。

统一收敛原先散落在 `OSSService.*_object_path` 与 `LocalFileManager.build_*_path`
的两套路径规则。所有 key 都是 **统一虚拟路径**，第一段为 `{space_id}`，
后端（S3 / Local）自行决定如何落地。
"""

import time
from datetime import datetime
from uuid import UUID


def sanitize_filename(filename: str) -> str:
    """清洗文件名，防止目录遍历攻击。"""
    safe = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
    if not safe:
        safe = f"uploaded_file_{int(time.time())}"
    return safe


# ─── 知识库相关 ─────────────────────────────────────────────────────

def source_key(space_id: UUID | str, kbase_name: str, file_name: str) -> str:
    """源文件 key：{space_id}/{kbase}/documents/source/{file}"""
    return f"{space_id}/{kbase_name}/documents/source/{sanitize_filename(file_name)}"


def processed_key(space_id: UUID | str, kbase_name: str, file_name: str) -> str:
    """处理后文件 key。"""
    return f"{space_id}/{kbase_name}/documents/processed/{sanitize_filename(file_name)}"


def media_key(space_id: UUID | str, kbase_name: str, file_name: str) -> str:
    """chunk 媒体文件 key。"""
    return f"{space_id}/{kbase_name}/documents/processed/media/{sanitize_filename(file_name)}"


def kbase_init_keys(space_id: UUID | str, kbase_name: str) -> list[str]:
    """知识库初始化占位目录（key 尾部带 `/` 表示目录对象）。"""
    base = f"{space_id}/{kbase_name}"
    return [
        f"{base}/",
        f"{base}/images/",
        f"{base}/documents/source/",
        f"{base}/documents/processed/images/",
    ]


# ─── Space 图片 / Logo ──────────────────────────────────────────────

def space_image_key(space_id: UUID | str, file_name: str, ext: str) -> str:
    """空间内图片 key：{space_id}/images/{Y/M/D}/{name}"""
    date_seg = datetime.now().strftime("%Y/%m/%d")
    return f"{space_id}/images/{date_seg}/{sanitize_filename(file_name)}.{ext.lower()}"


def space_logo_key(space_id: UUID | str, file_name: str) -> str:
    """空间 logo key：{space_id}/logo/{name}"""
    return f"{space_id}/logo/{sanitize_filename(file_name)}"


# ─── 工具 ────────────────────────────────────────────────────────────

def split_namespace(key: str) -> tuple[str, str]:
    """把统一 key 拆成 (namespace, sub_key)。namespace 对应 S3 bucket / 本地一级目录。"""
    # public 资源走独立 namespace，兼容原 RustFSClient 中 "public/" 的特判
    if key.startswith("public/"):
        return "public", key[len("public/"):].lstrip("/")
    head, sep, rest = key.partition("/")
    if not sep:
        return head, ""
    return head, rest
