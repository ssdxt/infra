from __future__ import annotations

import enum

from sqlalchemy import (
    BigInteger, String, DateTime, UniqueConstraint, Index, Uuid, Column, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

from core.acl.schema import SubjectType, ResourceACLStatusEnum, ResourceACLActionEnum, ResourceRole, ResourceType


Base = declarative_base()


class ResourceACL(Base):
    """
    统一资源 ACL（资源实例级“例外授权”）
    - 默认权限来自 User.space_role（继承）
    - 只有需要特例（更细粒度共享/协作）时才写入这里
    """
    __tablename__ = "acl"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增主键")

    space_id = Column(
        Uuid,
        nullable=False,
        comment="Space ID（等同 tenant_id，所有 ACL 查询的隔离维度）",
    )

    subject_type = Column(
        Enum(SubjectType, native_enum=False, name="acl_subject_type_enum"),
        nullable=False,
        default=SubjectType.user,
        comment="授权主体类型：user/group",
    )
    subject_id = Column(
        Uuid,
        nullable=False,
        comment="授权主体ID：user_id 或 group_id",
    )

    resource_type = Column(
        Enum(ResourceType, native_enum=False, name="acl_resource_type_enum"),
        nullable=False,
        comment="资源类型：kbase/document 等",
    )
    resource_id = Column(
        Uuid,
        nullable=False,
        comment="资源ID：KnowledgeBase.uuid / Document.uuid",
    )

    role = Column(
        Enum(ResourceRole, native_enum=False, name="acl_resource_role_enum"),
        nullable=False,
        comment="主体在该资源上的角色：owner/admin/editor/viewer",
    )

    effect = Column(
        Enum(ResourceACLActionEnum, native_enum=False, name="acl_effect_enum"),
        nullable=False,
        default=ResourceACLActionEnum.allow,
        comment="授权效果：allow 或 deny（deny 可用于黑名单/收回继承权限）",
    )

    status = Column(
        Enum(ResourceACLStatusEnum, native_enum=False, name="acl_status_enum"),
        nullable=False,
        default=ResourceACLStatusEnum.active,
        comment="授权状态：active/disabled 等",
    )

    grant_source = Column(
        String(255),
        nullable=True,
        comment="授权来源/备注：user_name, user_role 等",
    )

    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        # 同一 space 下，同一主体对同一资源只能有一条有效规则（避免重复）
        UniqueConstraint(
            "space_id",
            "subject_type",
            "subject_id",
            "resource_type",
            "resource_id",
            name="uq_acl_space_subject_resource",
        ),
        # 最常用校验索引：判断某用户对某资源是否有例外授权
        Index(
            "idx_acl_lookup",
            "space_id",
            "resource_type",
            "resource_id",
            "subject_type",
            "subject_id",
            "status",
        ),
        # 反查：列出用户对某类资源的例外授权
        Index(
            "idx_acl_subject",
            "space_id",
            "subject_type",
            "subject_id",
            "resource_type",
        ),
        # 管理端：列出资源有哪些授权主体
        Index(
            "idx_acl_resource",
            "space_id",
            "resource_type",
            "resource_id",
            "role",
        ),
    )