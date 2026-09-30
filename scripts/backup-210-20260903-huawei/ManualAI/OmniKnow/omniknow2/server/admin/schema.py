from uuid import UUID

from pydantic import BaseModel, Field
from enum import Enum

from core.acl.schema import ResourceACLActionEnum


# ── 资源用户组 ──────────────────────────────────────────

class ResourceACLStatusEnum(str, Enum):
    active = "active"
    disabled = "disabled"

class ResourceRole(str, Enum):
    owner = "owner"
    admin = "admin"
    editor = "editor"
    viewer = "viewer"

class ResourceACLEnum(str, Enum):
    allow = "allow"
    deny = "deny"

class ResourceGroupCreateRequest(BaseModel):
    name: str = Field(..., max_length=128, description="用户组名称")
    description: str | None = Field(None, max_length=512, description="用户组描述")


class ResourceGroupUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=128, description="用户组名称")
    description: str | None = Field(None, max_length=512, description="用户组描述")
    status: str | None = Field(None, pattern=r"^(active|disabled)$", description="状态：active/disabled")


# ── 组成员 ──────────────────────────────────────────────

class GroupMemberAddRequest(BaseModel):
    user_ids: list[UUID] = Field(..., min_length=1, description="批量添加的用户ID列表")


class GroupMemberRemoveRequest(BaseModel):
    user_ids: list[UUID] = Field(..., min_length=1, description="批量移除的用户ID列表")


# ── 组权限绑定（操作 ResourceACL，subject_type="group"）──

class GroupPermissionBindRequest(BaseModel):
    resource_type: str = Field(..., description="资源类型：knowledge_base / document / model_3d")
    resource_id: UUID = Field(..., description="资源ID")
    role: str = Field(..., description="角色：owner/admin/editor/viewer")
    effect: str = Field("allow", pattern=r"^(allow|deny)$", description="授权效果：allow/deny")


class GroupPermissionUnbindRequest(BaseModel):
    resource_type: str = Field(..., description="资源类型")
    resource_id: UUID = Field(..., description="资源ID")



# ── 用户管理 ────────────────────────────────────────────

class AdminUserStatusRequest(BaseModel):
    status: int = Field(..., description="用户状态：1=启用，0=禁用")


class AdminUserRoleRequest(BaseModel):
    role_code: str = Field(..., description="角色代码，如 admin, user")

class AdminUserCreateRequest(BaseModel):
    name: str = Field(..., max_length=255, description="用户姓名")
    password: str = Field(..., min_length=8, max_length=255, description="密码，至少8位")
    account: str = Field(..., max_length=255, description="用户名")


# ── RBAC 角色 ──────────────────────────────────────────

class RoleCreateRequest(BaseModel):
    name: str = Field(..., max_length=255, description="角色名称")
    code: str = Field(..., max_length=255, description="角色编码")
    scope: str = Field("space", max_length=255, description="角色作用域")
    description: str | None = Field(None, description="角色描述")


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=255, description="角色名称")
    description: str | None = Field(None, description="角色描述")
    status: int | None = Field(None, ge=0, le=1, description="角色状态：1=启用，0=停用")


# ── RBAC 权限 ──────────────────────────────────────────

class PermissionCreateRequest(BaseModel):
    name: str = Field(..., max_length=255, description="权限名称")
    code: str = Field(..., max_length=255, description="权限编码")
    description: str | None = Field(None, description="权限描述")


class PermissionUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=255, description="权限名称")
    description: str | None = Field(None, description="权限描述")
    status: int | None = Field(None, ge=0, le=1, description="权限状态：1=启用，0=停用")


# ── 角色-权限绑定 ──────────────────────────────────────

class RolePermissionBindRequest(BaseModel):
    permission_ids: list[UUID] = Field(..., min_length=1, description="批量绑定的权限ID列表")


class RolePermissionUnbindRequest(BaseModel):
    permission_ids: list[UUID] = Field(..., min_length=1, description="批量解绑的权限ID列表")


# ── 用户-角色绑定 ──────────────────────────────────────

class UserRoleBindRequest(BaseModel):
    role_ids: list[UUID] = Field(..., min_length=1, description="批量绑定的角色ID列表")


class UserRoleUnbindRequest(BaseModel):
    role_ids: list[UUID] = Field(..., min_length=1, description="批量解绑的角色ID列表")
