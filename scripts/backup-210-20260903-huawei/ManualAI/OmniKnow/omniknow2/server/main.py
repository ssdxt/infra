import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from utils.log import logger

from exceptions.handlers import register_exception_handlers
from api.routers import router, dev_router
from core.config import settings
from core import startup
from middleware import register_middleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        if not settings.env.debug:
            logger.info("🚀 启动中，正在初始化配置...")
            await startup.check_db_connection()
            await startup.check_and_init_database()
            await startup.check_redis_connection()
            await startup.check_rsa_keys()
            await startup.check_oss_connection()
            await startup.check_parse_api_server()
        else:
            logger.info("⚠️ 开发者模式已启动。")
            logger.warning("开发者热重载模式下跳过初始化检查！")
        yield
    except Exception as e:
        raise e

def create_app() -> FastAPI:
    _app = FastAPI(title=settings.env.project_name,
                   version=settings.env.version,
                   lifespan=lifespan)

    # 注册中间件
    register_middleware(_app)

    # 注册事件
    # events.register_events(app)

    # 注册异常处理器
    register_exception_handlers(_app)

    # 注册路由
    _app.include_router(router)

    if settings.env.debug:
        _app.include_router(dev_router)

    return _app

app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app",
                host=settings.env.host,
                port=settings.env.port,
                reload=settings.env.debug,
                workers=settings.env.workers)
