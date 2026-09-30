from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    BigInteger, String, DateTime, UniqueConstraint, Index, Uuid, Column
)
from sqlalchemy.sql import func

from db.models.acl import Base


class ResourceGroup(Base):
    """
    资源用户组 —— 用于资源级 ACL 的分组授权。
    与 RBAC 的 Roles 完全独立：Roles 管系统操作权限，ResourceGroup 管资源实例权限。
    """
    __tablename__ = "resource_group"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增主键")
    uuid = Column(Uuid, nullable=False, unique=True, default=uuid4, comment="业务主键")
    space_id = Column(Uuid, nullable=False, comment="所属空间ID")
    name = Column(String(128), nullable=False, comment="用户组名称")
    description = Column(String(512), nullable=True, comment="用户组描述")
    status = Column(String(16), nullable=False, default="active", comment="状态：active/disabled/deleted")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("space_id", "name", name="uq_resource_group_space_name"),
        Index("idx_resource_group_space", "space_id", "status"),
    )


class ResourceGroupMember(Base):
    """
    资源用户组成员关系表
    """
    __tablename__ = "resource_group_member"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增主键")
    group_id = Column(Uuid, nullable=False, comment="ResourceGroup.uuid")
    user_id = Column(Uuid, nullable=False, comment="User.uuid")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
        Index("idx_group_member_group", "group_id"),
        Index("idx_group_member_user", "user_id"),
    )
