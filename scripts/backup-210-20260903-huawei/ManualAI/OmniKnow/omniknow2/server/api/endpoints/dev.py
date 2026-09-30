from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import os
import uuid
from uuid import UUID
import hashlib

from schemas.public import ResponseModel
from utils import hash_sha512
from utils.public import str_to_base64
from db.session import get_session
from db.session import async_engine
from db.models.public import *  # 需要导入models
from db.models.acl import Base as AclBase  # 单独导入 AclBase，避免覆盖主 Base
from db.models.acl import ResourceACL  # noqa: F401
from db.session import Base  # 显式导入主 Base，防止被 acl 的 Base 覆盖
from db.models.rag import (Space,
                           User,
                           Tenant,
                           Department,
                           Position,
                           Resource,
                           Chunk,
                           UserDetail,
                           KnowledgeBase,
                           Agent,
                           ChatMessage,
                           Conversation,
                           DefaultQuestion,
                           ChatResource
                           )  # 需要导入models
from db.models.rbac import (
    Permission,
    RolePermission,
    Roles,
    UserRole,
)

from exceptions.base_errors import UnknowError
from schemas.user import UserRegisterSchema

router = APIRouter()


@router.get("/create_all")
async def create_all():
    """
    ORM模型映射模型表
    """
    # 必须导入所有 ORM 模型模块，才能让它们注册到 Base.metadata
    # 否则未被 import 的模型对应的表不会被创建
    from memory.model import Memory  # noqa: F401
    from audit.model import ActivityLog  # noqa: F401
    from audit.access_model import AccessLog  # noqa: F401
    from db.models.logs import UploadEvent  # noqa: F401
    from db.models.acl import ResourceACL  # noqa: F401
    from admin.model import ResourceGroup, ResourceGroupMember  # noqa: F401
    from image.model import Image  # noqa: F401
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(AclBase.metadata.create_all)
    return {"message": "表格创建成功", "code": 200}


@router.get("/failed")
async def failed():
    """
    测试失败请求
    """
    raise UnknowError(message="测试异常")


@router.post("/{space_id}/new_user")
async def new_user(
        space_id: UUID,
        user: UserRegisterSchema,
        db: AsyncSession = Depends(get_session)
) -> ResponseModel:
    """
    创建用户
    """
    salt = os.urandom(32)
    # password_b64 = str_to_base64(user.password)
    msg = f"{user.password}{salt.hex()}"
    secret = hash_sha512(msg)
    user_orm = User(
        space_id=space_id,
        space_role="member",
        name=user.name,
        account=user.account,
        password=secret,
        salt=str(salt.hex()),
        source="超真云",
    )
    db.add(user_orm)
    await db.commit()
    return ResponseModel.success(data={
        "uuid": str(user_orm.uuid),
    })


@router.get("/add_permission")
async def add_permission(
        name: str,
        code: str,
        db: AsyncSession = Depends(get_session)
) -> ResponseModel:
    """
    添加权限
    """
    async with db:
        permission = Permission(
            name=name,
            code=code,
        )
        db.add(permission)
        await db.commit()
        await db.refresh(permission)
    return ResponseModel.success()
