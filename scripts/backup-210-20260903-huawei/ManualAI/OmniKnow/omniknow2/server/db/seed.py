"""
种子数据：当数据库为空时，写入默认管理员用户、默认空间及关联关系。
"""

import os
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.rag import User, Space
from db.models.rbac import UserRole
from db.rbac_seed import sync_rbac_baseline
from storage.factory import get_storage
from utils.public import hash_md5
from utils.crypto import encode_password
from utils.log import logger


async def seed_default_data(session: AsyncSession) -> None:
    """在一个事务中写入所有默认种子数据。"""

    # 1. 同步默认角色与权限
    role_map, _ = await sync_rbac_baseline(session)

    # 2. 创建默认管理员用户
    init_cfg = settings.init
    salt = os.urandom(32).hex()
    password_hash = await encode_password(init_cfg.admin_password, salt)

    admin_user = User(
        name=init_cfg.admin_name,
        account=init_cfg.admin_account,
        password=password_hash,
        salt=salt,
        role=0,          # 超管
        source="本地注册",
    )
    session.add(admin_user)
    await session.flush()
    logger.info(f"✅ 已创建默认管理员用户: {admin_user.account}")

    # 3. 创建默认空间
    space_name = init_cfg.space_name
    code = hash_md5(space_name + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    default_space = Space(
        name=space_name,
        description="系统默认空间",
        owner=admin_user.uuid,
        code=code,
    )
    session.add(default_space)
    await session.flush()
    logger.info(f"✅ 已创建默认空间: {default_space.name}")

    # 4. 管理员绑定到默认空间（owner）
    admin_user.space_id = default_space.uuid
    admin_user.space_role = "owner"

    # 5. 管理员绑定 superadmin 角色
    user_role = UserRole(
        user_id=admin_user.uuid,
        role_id=role_map["superadmin"].uuid,
    )
    session.add(user_role)

    await session.flush()
    await session.commit()
    logger.info("✅ 已完成管理员与空间、角色的关联")

    # 6. 初始化默认空间的存储 bucket（与 SpaceService.create_space 保持一致）
    await get_storage().ensure_space_bucket(default_space.uuid)
    logger.info(f"✅ 已初始化默认空间存储 bucket: {default_space.uuid}")
