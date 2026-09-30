"""StorageService 工厂：根据配置构造单例。"""

from core.config import AppSettings, settings as global_settings
from storage.backend import StorageBackend
from storage.backends.local import LocalBackend
from storage.backends.s3 import S3Backend
from storage.cache import Md5PathCache
from storage.service import StorageService

_INSTANCE: StorageService | None = None


def get_storage() -> StorageService:
    """获取全局单例 StorageService（首次调用时按配置构建）。"""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = build_storage_service()
    return _INSTANCE


def reset_storage() -> None:
    """测试场景重置单例。"""
    global _INSTANCE
    _INSTANCE = None


def _s3_endpoint(host: str, port: int, ssl: int | None) -> str:
    protocol = "https" if ssl else "http"
    return f"{protocol}://{host}:{port}"


def build_storage_service(settings: AppSettings | None = None) -> StorageService:
    """根据配置构建 `StorageService` 单例。

    - `storage.backend == "s3"`：读写走内网 S3，预签名走 wan 地址。
    - `storage.backend == "local"`：读写、预签名都使用 LocalBackend。
    - 本地暂存（scratch）始终启用，目录沿用 `settings.parser.file_path`。
    """
    settings = settings or global_settings

    scratch = LocalBackend(base_path=settings.parser.file_path)

    backend: StorageBackend
    presign_backend: StorageBackend
    public_url_base: str | None = None

    if settings.storage.backend == "local":
        local_cfg = settings.storage.local
        backend = LocalBackend(
            base_path=local_cfg.base_path,
            public_url_prefix=local_cfg.public_url_prefix,
        )
        presign_backend = backend
        public_url_base = local_cfg.public_url_prefix
    else:
        oss = settings.oss
        backend = S3Backend(
            endpoint=_s3_endpoint(oss.host, oss.port, oss.ssl),
            access_key=oss.access_key,
            secret_key=oss.secret_key,
            region=oss.region,
        )
        wan_ssl = 1 if (oss.ssl or oss.wan_port == 443) else 0
        presign_backend = S3Backend(
            endpoint=_s3_endpoint(oss.wan_host, oss.wan_port, wan_ssl),
            access_key=oss.access_key,
            secret_key=oss.secret_key,
            region=oss.region,
        )
        protocol = "https" if wan_ssl else "http"
        public_url_base = f"{protocol}://{oss.wan_host}:{oss.wan_port}"

    cache = Md5PathCache() if settings.storage.enable_md5_cache else None

    return StorageService(
        backend=backend,
        presign_backend=presign_backend,
        scratch=scratch,
        cache=cache,
        public_url_base=public_url_base,
    )
