from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from core.config import settings


host = settings.database.host
port = settings.database.port
database = settings.database.database
user = settings.database.user
password = settings.database.password

if settings.database.type == "pg":
    SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
elif settings.database.type == "mysql":
    SQLALCHEMY_DATABASE_URL = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
else:
    raise Exception("数据库类型错误")

Base = declarative_base()

# 创建异步引擎
async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=settings.env.sql_debug,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建异步Session工厂
async_session = async_sessionmaker(
    async_engine,
    expire_on_commit=False
)


# 依赖注入 - 获取 Session
async def get_session() -> AsyncGenerator[AsyncSession, Any]:
    async with async_session() as session:
        yield session
