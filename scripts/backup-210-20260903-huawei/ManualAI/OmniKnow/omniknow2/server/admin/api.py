from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.dependencies import RequestContext, authorize
from audit.spec import AuditSpec
from schemas.public import ResponseModel
from admin.schema import (
    ResourceGroupCreateRequest,
    ResourceGroupUpdateRequest,
    GroupMemberAddRequest,
    GroupMemberRemoveRequest,
    GroupPermissionBindRequest,
    GroupPermissionUnbindRequest,
    AdminUserStatusRequest,
    AdminUserRoleRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
    PermissionCreateRequest,
    PermissionUpdateRequest,
    RolePermissionBindRequest,
    RolePermissionUnbindRequest,
    UserRoleBindRequest,
    UserRoleUnbindRequest, AdminUserCreateRequest,
)
from admin.service import ResourceGroupService, AdminUserService
from admin.rbac_service import RBACService


router = APIRouter()


# ── 资源用户组 CRUD ─────────────────────────────────────

@router.get("/spaces/{space_id}/admin/resource-groups")
async def list_groups(
    space_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: Optional[str] = Query(None),
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 资源用户组列表"""
    sid = space_id or ctx.user.uuid  # fallback 由 service 层处理
    res = await ResourceGroupService(ctx).list_groups(sid, page, page_size, keyword)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/resource-groups")
async def create_group(
    req: ResourceGroupCreateRequest,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 创建资源用户组"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).create_group(sid, req)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/admin/resource-groups/{group_id}")
async def get_group_detail(
    group_id: UUID,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 资源用户组详情"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).get_group_detail(sid, group_id)
    return ResponseModel.success(res)


@router.put("/spaces/{space_id}/admin/resource-groups/{group_id}")
async def update_group(
    group_id: UUID,
    req: ResourceGroupUpdateRequest,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 更新资源用户组"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).update_group(sid, group_id, req)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/resource-groups/{group_id}")
async def delete_group(
    group_id: UUID,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 删除资源用户组（级联清理成员和权限）"""
    sid = space_id or ctx.user.uuid
    await ResourceGroupService(ctx).delete_group(sid, group_id)
    return ResponseModel.success()


# ── 组成员管理 ──────────────────────────────────────────

@router.get("/spaces/{space_id}/admin/resource-groups/{group_id}/members")
async def list_members(
    space_id: UUID,
    group_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 资源用户组成员列表"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).list_members(sid, group_id, page, page_size)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/resource-groups/{group_id}/members")
async def add_members(
    group_id: UUID,
    req: GroupMemberAddRequest,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 批量添加组成员"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).add_members(sid, group_id, req)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/resource-groups/{group_id}/members")
async def remove_members(
    group_id: UUID,
    req: GroupMemberRemoveRequest,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 批量移除组成员"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).remove_members(sid, group_id, req)
    return ResponseModel.success(res)


# ── 组权限绑定 ──────────────────────────────────────────

@router.get("/spaces/{space_id}/admin/resource-groups/{group_id}/permissions")
async def list_group_permissions(
    group_id: UUID,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 资源用户组权限列表"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).list_group_permissions(sid, group_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/resource-groups/{group_id}/permissions")
async def bind_permission(
    group_id: UUID,
    req: GroupPermissionBindRequest,
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 绑定资源权限到用户组"""
    sid = space_id or ctx.user.uuid
    res = await ResourceGroupService(ctx).bind_permission(sid, group_id, req)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/resource-groups/{group_id}/permissions")
async def unbind_permission(
    space_id: UUID,
    group_id: UUID,
    req: GroupPermissionUnbindRequest,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 解绑资源用户组权限"""
    sid = space_id or ctx.user.uuid
    await ResourceGroupService(ctx).unbind_permission(sid, group_id, req)
    return ResponseModel.success()


# ── 用户管理 ────────────────────────────────────────────

@router.get("/spaces/{space_id}/admin/users")
async def list_users(
    space_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: Optional[str] = Query(None),
    status: Optional[int] = Query(None),
    ctx: RequestContext = Depends(authorize("admin:user:manage")),
) -> ResponseModel:
    """管理员 - 用户列表（分页、搜索、筛选）"""
    res = await AdminUserService(ctx).list_users(space_id, page, page_size, keyword, status)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/admin/users/{user_id}")
async def get_user_detail(
    space_id: UUID,
    user_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:user:manage")),
) -> ResponseModel:
    """管理员 - 用户详情"""
    res = await AdminUserService(ctx).get_user_detail(space_id, user_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/users")
async def create_user(
    space_id: UUID,
    req: AdminUserCreateRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:user:manage",
        audit=AuditSpec(action="user_create", target_type="user"),
    )),
) -> ResponseModel:
    """管理员 - 创建用户"""
    res = await AdminUserService(ctx).create_user(space_id, req)
    ctx.audit_detail = {"_target_id": res["uuid"], "account": res["account"], "name": res["name"]}
    return ResponseModel.success(res)


@router.patch("/spaces/{space_id}/admin/users/{user_id}/status")
async def update_user_status(
    space_id: UUID,
    user_id: UUID,
    req: AdminUserStatusRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:user:manage",
        audit=AuditSpec(action="user_status_change", target_type="user"),
    )),
) -> ResponseModel:
    """管理员 - 封禁/启用用户"""
    await AdminUserService(ctx).update_user_status(space_id, user_id, req)
    ctx.audit_detail = {"new_status": req.status}
    return ResponseModel.success()


@router.patch("/spaces/{space_id}/admin/users/{user_id}/role")
async def update_user_role(
    space_id: UUID,
    user_id: UUID,
    req: AdminUserRoleRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:user:manage",
        audit=AuditSpec(action="user_role_change", target_type="user"),
    )),
) -> ResponseModel:
    """管理员 - 变更用户角色"""
    await AdminUserService(ctx).update_user_role(space_id, user_id, req)
    ctx.audit_detail = {"new_role": req.role_code}
    return ResponseModel.success()


@router.delete("/spaces/{space_id}/admin/users/{user_id}")
async def delete_user(
    space_id: UUID,
    user_id: UUID,
    ctx: RequestContext = Depends(authorize(
        "admin:user:manage",
        audit=AuditSpec(action="user_delete", target_type="user"),
    )),
) -> ResponseModel:
    """管理员 - 软删用户"""
    await AdminUserService(ctx).delete_user(space_id, user_id)
    return ResponseModel.success()


@router.get("/spaces/{space_id}/admin/permissions")
async def list_permissions(
    space_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:acl:manage")),
) -> ResponseModel:
    """管理员 - 权限列表"""
    res = await ResourceGroupService(ctx).list_permissions(space_id)
    return ResponseModel.success(res)


# ── RBAC 角色 CRUD ──────────────────────────────────────

@router.get("/spaces/{space_id}/admin/group/roles")
async def list_rbac_roles(
    space_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: Optional[str] = Query(None),
    ctx: RequestContext = Depends(authorize("admin:rbac:manage")),
) -> ResponseModel:
    """管理员 - RBAC 角色列表"""
    res = await RBACService(ctx).list_roles(space_id, page, page_size, keyword)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/group/roles")
async def create_rbac_role(
    space_id: UUID,
    req: RoleCreateRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_create", target_type="role"),
    )),
) -> ResponseModel:
    """管理员 - 新建 RBAC 角色"""
    res = await RBACService(ctx).create_role(space_id, req)
    ctx.audit_detail = {"_target_id": res["uuid"], "code": res["code"], "name": res["name"]}
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/admin/group/roles/{role_id}")
async def get_rbac_role_detail(
    space_id: UUID,
    role_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:rbac:manage")),
) -> ResponseModel:
    """管理员 - RBAC 角色详情（含已绑定权限）"""
    res = await RBACService(ctx).get_role_detail(space_id, role_id)
    return ResponseModel.success(res)


@router.put("/spaces/{space_id}/admin/group/roles/{role_id}")
async def update_rbac_role(
    space_id: UUID,
    role_id: UUID,
    req: RoleUpdateRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_update", target_type="role"),
    )),
) -> ResponseModel:
    """管理员 - 更新 RBAC 角色"""
    res = await RBACService(ctx).update_role(space_id, role_id, req)
    ctx.audit_detail = req.model_dump(exclude_none=True)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/group/roles/{role_id}")
async def delete_rbac_role(
    space_id: UUID,
    role_id: UUID,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_delete", target_type="role"),
    )),
) -> ResponseModel:
    """管理员 - 软删 RBAC 角色（内置角色不可删）"""
    await RBACService(ctx).delete_role(space_id, role_id)
    return ResponseModel.success()


# ── RBAC 权限 CRUD ──────────────────────────────────────

@router.get("/spaces/{space_id}/admin/group/permissions")
async def list_rbac_permissions(
    space_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: Optional[str] = Query(None),
    ctx: RequestContext = Depends(authorize("admin:rbac:manage")),
) -> ResponseModel:
    """管理员 - RBAC 权限列表"""
    res = await RBACService(ctx).list_permissions(space_id, page, page_size, keyword)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/group/permissions")
async def create_rbac_permission(
    space_id: UUID,
    req: PermissionCreateRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="permission_create", target_type="permission"),
    )),
) -> ResponseModel:
    """管理员 - 新建 RBAC 权限"""
    res = await RBACService(ctx).create_permission(space_id, req)
    ctx.audit_detail = {"_target_id": res["uuid"], "code": res["code"], "name": res["name"]}
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/admin/group/permissions/{permission_id}")
async def get_rbac_permission_detail(
    space_id: UUID,
    permission_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:rbac:manage")),
) -> ResponseModel:
    """管理员 - RBAC 权限详情"""
    res = await RBACService(ctx).get_permission_detail(space_id, permission_id)
    return ResponseModel.success(res)


@router.put("/spaces/{space_id}/admin/group/permissions/{permission_id}")
async def update_rbac_permission(
    space_id: UUID,
    permission_id: UUID,
    req: PermissionUpdateRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="permission_update", target_type="permission"),
    )),
) -> ResponseModel:
    """管理员 - 更新 RBAC 权限"""
    res = await RBACService(ctx).update_permission(space_id, permission_id, req)
    ctx.audit_detail = req.model_dump(exclude_none=True)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/group/permissions/{permission_id}")
async def delete_rbac_permission(
    space_id: UUID,
    permission_id: UUID,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="permission_delete", target_type="permission"),
    )),
) -> ResponseModel:
    """管理员 - 软删 RBAC 权限（系统内置权限不可删）"""
    await RBACService(ctx).delete_permission(space_id, permission_id)
    return ResponseModel.success()


# ── RBAC 角色-权限绑定 ──────────────────────────────────

@router.get("/spaces/{space_id}/admin/group/roles/{role_id}/permissions")
async def list_rbac_role_permissions(
    space_id: UUID,
    role_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:rbac:manage")),
) -> ResponseModel:
    """管理员 - 角色已绑定权限列表"""
    res = await RBACService(ctx).list_role_permissions(space_id, role_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/group/roles/{role_id}/permissions")
async def bind_rbac_role_permissions(
    space_id: UUID,
    role_id: UUID,
    req: RolePermissionBindRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_permission_bind", target_type="role"),
    )),
) -> ResponseModel:
    """管理员 - 批量绑定权限到角色"""
    res = await RBACService(ctx).bind_role_permissions(space_id, role_id, req)
    ctx.audit_detail = {"permission_ids": [str(pid) for pid in req.permission_ids]}
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/group/roles/{role_id}/permissions")
async def unbind_rbac_role_permissions(
    space_id: UUID,
    role_id: UUID,
    req: RolePermissionUnbindRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_permission_unbind", target_type="role"),
    )),
) -> ResponseModel:
    """管理员 - 批量解绑角色权限"""
    res = await RBACService(ctx).unbind_role_permissions(space_id, role_id, req)
    ctx.audit_detail = {"permission_ids": [str(pid) for pid in req.permission_ids]}
    return ResponseModel.success(res)


# ── 用户-角色增量绑定 ───────────────────────────────────

@router.get("/spaces/{space_id}/admin/users/{user_id}/roles")
async def list_user_rbac_roles(
    space_id: UUID,
    user_id: UUID,
    ctx: RequestContext = Depends(authorize("admin:user:manage")),
) -> ResponseModel:
    """管理员 - 用户已绑定的 RBAC 角色列表"""
    res = await RBACService(ctx).list_user_roles(space_id, user_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/admin/users/{user_id}/roles")
async def add_user_rbac_roles(
    space_id: UUID,
    user_id: UUID,
    req: UserRoleBindRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:user:manage",
        audit=AuditSpec(action="user_role_bind", target_type="user"),
    )),
) -> ResponseModel:
    """管理员 - 给用户增量绑定角色"""
    res = await RBACService(ctx).add_user_roles(space_id, user_id, req)
    ctx.audit_detail = {"role_ids": [str(rid) for rid in req.role_ids]}
    return ResponseModel.success(res)

@router.post("/spaces/{space_id}/admin/groups/{group_id}/members")
async def add_group_membership(
    space_id: UUID,
    group_id: UUID,
    req: GroupMemberAddRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_member_bind", target_type="role", target_param="group_id"),
    )),
) -> ResponseModel:
    """管理员 - 给 RBAC 组批量增加成员"""
    res = await RBACService(ctx).add_members(space_id, group_id, req)
    ctx.audit_detail = {"user_ids": [str(uid) for uid in req.user_ids]}
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/groups/{group_id}/members")
async def remove_group_membership(
    space_id: UUID,
    group_id: UUID,
    req: GroupMemberRemoveRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:rbac:manage",
        audit=AuditSpec(action="role_member_unbind", target_type="role", target_param="group_id"),
    )),
) -> ResponseModel:
    """管理员 - 给 RBAC 组批量移除成员"""
    res = await RBACService(ctx).remove_members(space_id, group_id, req)
    ctx.audit_detail = {"user_ids": [str(uid) for uid in req.user_ids]}
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/admin/users/{user_id}/roles")
async def remove_user_rbac_roles(
    space_id: UUID,
    user_id: UUID,
    req: UserRoleUnbindRequest,
    ctx: RequestContext = Depends(authorize(
        "admin:user:manage",
        audit=AuditSpec(action="user_role_unbind", target_type="user"),
    )),
) -> ResponseModel:
    """管理员 - 移除用户的指定角色"""
    res = await RBACService(ctx).remove_user_roles(space_id, user_id, req)
    ctx.audit_detail = {"role_ids": [str(rid) for rid in req.role_ids]}
    return ResponseModel.success(res)
