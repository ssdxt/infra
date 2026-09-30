from __future__ import annotations

import enum
from enum import Enum


class ResourceType(str, Enum):
    doc = "doc"
    model3d = "model3d"
    rich_text = "rich_text"
    video = "video"
    audio = "audio"
    image = "image"
    dataset = "dataset"
    kbase = "kbase"


class ResourceStatus(str, Enum):
    pending = "pending"  # 审批中
    rejected = "rejected"  # 已驳回
    parsing = "parsing"  # 处理中
    received = "received"  # 已入库
    failed = "failed"  # 解析失败
    archived = "archived"  # 已归档
    destroyed = "destroyed"  # 已销毁
    completed = "completed"  # 解析完成


class RagStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"


class Action(str, Enum):
    space_view = "space:view"
    space_edit = "space:edit"
    space_delete = "space:delete"

    kbase_view = "knowledge_base:view"
    kbase_edit = "knowledge_base:edit"
    kbase_upload = "knowledge_base:upload"
    kbase_delete = "knowledge_base:delete"
    kbase_parse = "knowledge_base:parse"

    doc_read = "document:read"
    doc_upload = "document:write"
    doc_delete = "document:delete"
    model_3d_read = "model_3d:read"


# 角色等级（从低到高）
SPACE_ROLE_ORDER = {
    "viewer": 10,
    "member": 20,
    "editor": 30,
    "admin": 40,
    "owner": 50,
}

RESOURCE_ROLE_ORDER = {
    "viewer": 10,
    "editor": 30,
    "admin": 40,
    "owner": 50,
}


class SpaceRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class SubjectType(str, enum.Enum):
    user = "user"
    group = "group"  # 可选扩展


class ResourceACLStatusEnum(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class ResourceACLActionEnum(str, enum.Enum):
    allow = "allow"
    deny = "deny"


class ResourceRole(str, enum.Enum):
    """
    资源内角色（例外授权用）
    通常可以与 SpaceRole 保持相同集合，便于统一 policy。
    """
    owner = "owner"
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


# Action → 最低所需角色
ACTION_POLICY = {
    Action.space_delete: {
        "fallback": SpaceRole.owner,
    },

    Action.space_edit: {
        "fallback": SpaceRole.admin,
    },
    Action.space_view: {
        "fallback": SpaceRole.member,
    },

    Action.kbase_view:  {
        "resource": ResourceRole.viewer,
        "fallback": SpaceRole.member,
    },
    Action.kbase_edit: {
        "resource": ResourceRole.editor,
        "fallback": SpaceRole.admin,
    },

    Action.kbase_delete: {
        "resource": ResourceRole.admin,
        "fallback": SpaceRole.admin,
    },

    Action.kbase_upload: {
        "fallback": SpaceRole.member
    },
    Action.doc_read: {
        "resource": ResourceRole.viewer,
        "fallback": SpaceRole.member,
    },
    Action.doc_upload: {
        "resource": ResourceRole.editor,
        "fallback": SpaceRole.admin,
    },
    Action.doc_delete: {
        "resource": ResourceRole.owner,
        "fallback": SpaceRole.admin,
    },
    Action.kbase_parse: {
        "resource": ResourceRole.editor,
        "fallback": SpaceRole.admin,
    }
}