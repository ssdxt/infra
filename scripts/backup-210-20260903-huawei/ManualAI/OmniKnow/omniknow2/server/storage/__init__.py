"""统一存储模块。

业务代码应 **只** 依赖 `StorageService`，禁止直接 import 具体后端或 aioboto3。
"""

from storage.factory import build_storage_service, get_storage, reset_storage
from storage.service import StorageService
from storage.types import ObjectStat, SavedFile

__all__ = [
    "StorageService",
    "SavedFile",
    "ObjectStat",
    "build_storage_service",
    "get_storage",
    "reset_storage",
]
