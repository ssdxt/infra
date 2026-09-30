import os

import aiohttp
from sqlalchemy import text
from redis.asyncio import Redis
from botocore.exceptions import ConnectTimeoutError, ClientError

from core.config import settings
from db.session import async_engine
from db.init_db import init_database
from utils.log import logger
from storage import get_storage


async def check_db_connection():
    try:
        logger.info("正在尝试连接数据库...")
        # engine = create_async_engine(database_url, echo=True)
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("✅ 数据库连接成功！")
    except Exception as e:
        logger.error(str(e))
        raise RuntimeError(f"❎ 数据库连接失败，原因为：{e}") from e


async def check_and_init_database():
    """建表并在数据库为空时写入默认种子数据。"""
    try:
        await init_database()
    except Exception as e:
        logger.error(str(e))
        raise RuntimeError(f"❎ 数据库初始化失败，原因为：{e}") from e


async def check_redis_connection():
    try:
        logger.info("正在尝试连接 Redis...")
        redis = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password,
            db=settings.redis.db
        )
        await redis.ping()
        logger.info("✅ Redis 连接成功！")
    except Exception as e:
        logger.error(str(e))
        raise RuntimeError("❎ Redis 连接失败") from e


async def check_oss_connection():
    backend_type = settings.storage.backend
    try:
        logger.info(f"正在尝试连接存储后端 [{backend_type}]...")
        storage = get_storage()
        await storage.health_check()
        logger.info(f"✅ 存储后端 [{backend_type}] 连接成功！")
    except ConnectTimeoutError as e:
        raise RuntimeError(f"❎ 存储后端 [{backend_type}] 连接失败。") from e
    except ClientError as e:
        raise RuntimeError(
            f"❎ 存储后端 [{backend_type}] 连接成功但操作失败，请检查配置文件或网络设置。"
        ) from e
    except ConnectionRefusedError as e:
        raise RuntimeError(
            f"❎ 存储后端 [{backend_type}] 连接被拒绝，请检查服务是否启动或网络设置。"
        ) from e
    except Exception as e:
        logger.error(f"❎ 存储后端 [{backend_type}] 连接失败，原因为：{e}")
        raise RuntimeError(f"❎ 存储后端 [{backend_type}] 未知原因连接失败") from e


async def check_rsa_keys():
    """
    检查static下pem密钥文件是否存在
    :return:
    """
    path = None
    try:
        logger.info("正在检查密钥文件...")
        if not settings.env.debug:
            path = settings.env.rsa_file_path
            # with open('static/rsa_public_key.pem', 'r') as f:
            #     public_key = f.read()
            with open(path, 'r') as f:  # 仅检查私钥
                private_key = f.read()
            if not private_key:
                raise FileNotFoundError()
            else:
                logger.info("✅ 密钥文件检查成功！")
        else:
            logger.warning("开发者模式下跳过密钥检查！")
        return True
    except FileNotFoundError as e:
        logger.error(str(e))
        raise RuntimeError(f"❎ 目录 {path} 下rsa_private_key.pem文件不存在")


async def check_parse_api_server():
    """
    检查外部AI接口服务是否可用
    :return:
    """
    try:
        logger.info("正在尝试连接文档分析服务...")
        api_url = settings.parser.api_url + "/health"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=3) as response:
                if response.status == 200:
                    logger.info("✅ 文档分析服务连接成功！")
                else:
                    logger.error(f"❎ 文档分析服务连接失败，状态码：{response.status}")
                    # raise RuntimeError(f"❎ 外部AI接口服务连接失败，状态码：{response.status}")
    except Exception as e:
        logger.error(f"❎ 文档分析服务连接失败，原因为：{e}")
        # raise RuntimeError(f"❎ 外部AI接口服务连接失败，原因为：{e}") from e


# async def check_chat_api_server():
#     """
#     检查外部AI接口服务是否可用
#     :return:
#     """
#     import aiohttp
#
#     try:
#         logger.info("正在尝试连接聊天服务...")
#         api_url = settings.api.chat_url + "/docs"
#         async with aiohttp.ClientSession() as session:
#             async with session.get(api_url, timeout=3) as response:
#                 if response.status == 200:
#                     logger.info("✅ 聊天服务连接成功！")
#                 else:
#                     logger.error(f"❎ 聊天服务连接失败，状态码：{response.status}")
#                     # raise RuntimeError(f"❎ 聊天服务连接失败，状态码：{response.status}")
#     except Exception as e:
#         logger.error(f"❎ 聊天服务连接失败，原因为：{e}")
#         # raise RuntimeError(f"❎ 聊天服务连接失败，原因为：{e}") from e


# async def check_queue_connection():
#     """
#     检查消息队列连接是否可用
#     :return:
#     """
#     try:
#         logger.info("正在尝试连接消息队列...")
#         rabbitmq = RabbitMQClient()
#         connection = await rabbitmq.connect()
#         logger.info("✅ 消息队列连接成功！")
#         return connection
#     except Exception as e:
#         logger.error(f"❎ 消息队列连接失败，原因为：{e}")
#         raise RuntimeError(f"❎ 消息队列连接失败，原因为：{e}") from e