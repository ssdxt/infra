"""
数据库初始化入口：建表 + 判断是否需要写入种子数据。
"""

from sqlalchemy import select, func

from db.session import async_engine, async_session, Base as MainBase

# 导入所有 model，确保 metadata 已注册
from db.models.rag import (  # noqa: F401
    Tenant, Space, User, UserDetail,
    Department, Position, Agent,
    KnowledgeBase, Chunk, Resource,
    Conversation, ChatMessage, DefaultQuestion, ChatResource
)
from db.models.rbac import Roles, Permission, UserRole, RolePermission  # noqa: F401
from memory.model import Memory  # noqa: F401
from audit.model import ActivityLog  # noqa: F401
from audit.access_model import AccessLog  # noqa: F401
from db.models.logs import UploadEvent  # noqa: F401
from db.models.acl import Base as AclBase, ResourceACL  # noqa: F401
from admin.model import ResourceGroup, ResourceGroupMember  # noqa: F401
from image.model import Image  # noqa: F401

from db.rbac_seed import sync_rbac_baseline
from db.seed import seed_default_data
from utils.log import logger


async def init_database() -> None:
    """
    数据库初始化：
    1. 自动建表（已存在的表不会重建）
    2. 若 user 表为空，则写入默认种子数据
    """

    # ── 建表 ──────────────────────────────────────────────
    logger.info("正在检查并创建数据库表...")
    async with async_engine.begin() as conn:
        await conn.run_sync(MainBase.metadata.create_all)
        await conn.run_sync(AclBase.metadata.create_all)
    logger.info("✅ 数据库表检查完成")

    # ── 同步系统 RBAC 基线（角色/权限）────────────────────
    async with async_session() as session:
        logger.info("正在同步系统 RBAC 基线数据...")
        await sync_rbac_baseline(session)
        await session.commit()
        logger.info("✅ 系统 RBAC 基线同步完成")

    # ── 判断是否需要种子数据 ──────────────────────────────
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(User))
        user_count = result.scalar()

        if user_count and user_count > 0:
            logger.info(f"数据库已有 {user_count} 个用户，跳过初始化种子数据")
            return

        logger.info("数据库为空，开始写入默认种子数据...")
        await seed_default_data(session)
        logger.info("✅ 数据库初始化完成")
