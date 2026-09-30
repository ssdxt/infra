from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationError

from loguru import logger

#
from pydantic import (
    Field,
    BaseModel
)


class EnvSettings(BaseModel):
    secret_key: str  # JWT 签名密钥，必须配置且不能使用默认值，生产环境建议使用随机生成的 32 字节以上的字符串
    algorithm: str = 'HS256'  # JWT 签名算法，默认为 HS256
    expire_time: int = 1  # JWT 过期时间，单位小时，默认为 1 小时
    project_name: str = 'Omniknow2' # 应用名称
    version: str = '2.0.0'  # 应用版本号
    host: str = '0.0.0.0'  # 应用监听地址，默认为 0.0.0.0
    port: int = 4000  # 应用监听端口，默认为 4000，生产环境建议使用反向代理（Nginx / Caddy）并关闭应用的直接公网访问
    debug: bool | None = False # 是否开启调试模式，开启后会自动重载代码并提供更详细的错误信息，适合开发环境使用
    workers: int = 1  # Gunicorn 工作进程数，默认为 1，生产环境根据运行压力自行调整
    rsa_file_path: str = 'static/rsa_private_key.pem'  # RSA 私钥文件路径
    sql_debug: bool | None = False  # SQLAlchemy 是否开启调试日志
    safe: bool | None = False  # 是否开启安全模式，开启后存储模块返回 URL 将使用签发的预签名 URL 而非直接路径。

#
class ParserSettings(BaseModel):
    api_url: str = 'http://127.0.0.1:8008'  # Worker 任务调度 API 地址
    file_path: str = './tmp/data/files/'  # Worker 解析文件的临时存储路径
    callback_secret: str | None = None  # Worker 回调鉴权密钥，可选
    callback_host: str | None = None  # Worker 任务完成/失败回调地址
    max_concurrent_tasks: int = 1  # 最大同时执行的文档解析任务数


class DatabaseSettings(BaseModel):
    type: str = 'mysql'  # 数据库类型，默认为 mysql，当前仅支持 MySQL、PostgreSQL
    host: str  # 数据库主机地址
    port: int  # 数据库端口
    user: str  # 数据库用户名
    password: str  # 数据库密码
    database: str  # 数据库名称


class RedisSettings(BaseModel):
    host: str  # Redis 主机地址
    port: int  # Redis 端口
    password: str | None = None  # Redis 密码，可选
    db: int | None = 0  # Redis 数据库索引，默认为 0，生产环境建议使用独立的数据库索引以避免与其他应用冲突
    task_db: int | None = 1  # Redis 任务队列数据库索引，默认为 1，生产环境建议使用独立的数据库索引以避免与其他应用冲突


class OssSettings(BaseModel):
    """S3 兼容对象存储配置（RustFS / MinIO / Aliyun OSS 等）。"""
    ssl: int | None = 0  # 是否启用 SSL，默认为 0（不启用），生产环境建议启用（设置为 1）
    type: str | None = 'minio'  # 存储类型，默认为 minio，当前仅支持 MinIO、RustFS
    host: str | None = '127.0.0.1'  # 存储服务内网地址，默认为本地地址
    wan_host: str | None = '192.168.1.100'  # 存储服务公网（局域网）地址
    port: int | None = 9000  # 存储服务API端口，默认为 9000
    wan_port: int | None = 9000  # 存储服务公网（局域网）API端口，默认为 9000，请做好防火墙规则或端口映射
    access_key: str | None = Field(None)  # 存储服务访问密钥，必须配置且不能使用默认值
    secret_key: str | None = Field(None)  # 存储服务访问密钥，必须配置且不能使用默认值
    region: str = 'eu-central-1'  # 存储服务区域，默认为 eu-central-1，某些 S3 兼容服务要求指定区域，在使用RustFS、MinIO时可保持默认


class LocalStorageSettings(BaseModel):
    """纯本地存储后端配置。"""
    base_path: str = './tmp/data/storage/'  # 本地存储根路径，所有文件都保存在这个目录下，当
    public_url_prefix: str | None = None   # 例如 http://host/files，可选


class StorageSettings(BaseModel):
    """统一存储模块配置。

    - `backend=s3` 时复用 `OssSettings`。
    - `backend=local` 时使用 `LocalStorageSettings`。
    """
    backend: Literal['s3', 'local'] = 's3'  # 存储后端类型，默认为 s3，当前支持 s3 和 local 两种存储后端
    enable_md5_cache: bool = True  # 是否启用 MD5 缓存，启用后会在 Redis 中缓存文件的 MD5 值以加速重复文件的处理，默认为 True
    local: LocalStorageSettings = LocalStorageSettings()  # 本地存储配置，仅在 backend=local 时使用


class NotifySettings(BaseModel):
    pipes: str | None
    bark_host: str | None = Field('https://api.day.app', examples=['https://api.day.app'])
    bark_token: str | None
    feishu_webhook: str | None = Field(None)
    feishu_secret: str | None = Field(None)
    dingtalk_webhook: str | None = Field(None)
    dingtalk_secret: str | None = Field(None)
    email_host: str | None = Field(None)
    email_port: int | None = Field(None)
    email_user: str | None = Field(None)
    email_password: str | None = Field(None)


class InitSettings(BaseModel):
    admin_account: str = 'su'  # 管理员账号，默认为 admin，生产环境建议修改为更复杂的账号名称
    admin_password: str = 'admin123'  # 管理员密码，默认为 admin123，生产环境强烈建议修改为更复杂的密码
    admin_name: str = '管理员'  # 管理员名称，默认为 管理员
    space_name: str = '默认空间'  # 默认空间名称，默认为 默认空间


class BasicSettings(BaseModel):
    timeout: int | None = Field(10, examples=[5, 10, 20], description="应用超时时间，默认为10秒")


class MilvusSettings(BaseModel):
    """Milvus 直连（pymilvus SDK）配置。"""
    ssl: int | None = 0  # 是否启用 SSL，默认为 0（不启用），生产环境建议启用（设置为 1）
    host: str = "127.0.0.1"
    port: int = 19530
    db_name: str = "default"
    token: str | None = None
    user: str | None = None
    password: str | None = None
    timeout: float = 30.0


class TrainingSettings(BaseModel):
    base_url: str = 'http://127.0.0.1:8000'  # 培训服务 API 地址
    timeout: int = 60  # 培训服务请求超时时间，单位秒，默认为 60 秒


class EmbedSettings(BaseModel):
    api_url: str = 'http://127.0.0.1:8021/v1'  # 嵌入模型 API 地址
    api_key: str | None = "cc"  # 嵌入模型 API 密钥，可选
    model_name: str = 'qwen-embedding'  # 嵌入模型名称，默认为 text-embedding-3-small，生产环境根据实际使用的嵌入模型调整
    dimension: int = 1024  # 嵌入向量维度，默认为 1024，生产环境根据实际使用的嵌入模型调整

class MemroySettings(BaseModel):
    limit: int = 3

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='_',
                                      env_nested_max_split=1,
                                      env_file='.env')

    env: EnvSettings
    parser: ParserSettings
    database: DatabaseSettings
    redis: RedisSettings
    oss: OssSettings
    storage: StorageSettings = StorageSettings()
    notify: NotifySettings
    basic: BasicSettings
    init: InitSettings = InitSettings()
    milvus: MilvusSettings = MilvusSettings()
    training: TrainingSettings = TrainingSettings()
    memory: MemroySettings = MemroySettings()
    embed: EmbedSettings = EmbedSettings()


try:
    settings = AppSettings.model_validate({})
except ValidationError as e:
    for err in e.errors():
        if err['type'] == 'missing':
            logger.error(f"配置项 {'.'.join(err['loc'])} 为空，请检查配置文件")
        elif err['type'] == 'int_parsing':
            logger.error(f"配置项 {'.'.join(err['loc'])} 要求为数值型，请检查配置文件")
        else:
            logger.error(f"配置项 {'.'.join(err['loc'])} 错误，请检查配置文件")
    logger.error("配置有误，程序退出...")
    exit(1)