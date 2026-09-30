from uuid import UUID
from typing import Optional

from core.dependencies import RequestContext
from core.permission_cache import refresh_user_permissions
from admin.rbac_repository import RBACRepository
from admin.error import (
    RoleNotFoundError,
    RoleCodeExistedError,
    BuiltinRoleProtectedError,
    PermissionNotFoundError,
    PermissionCodeExistedError,
    BuiltinPermissionProtectedError,
)
from admin.schema import (
    RoleCreateRequest,
    RoleUpdateRequest,
    PermissionCreateRequest,
    PermissionUpdateRequest,
    RolePermissionBindRequest,
    RolePermissionUnbindRequest,
    UserRoleBindRequest,
    UserRoleUnbindRequest, GroupMemberAddRequest, GroupMemberRemoveRequest,
)
from db.models.rbac import Roles, Permission
from db.rbac_seed import DEFAULT_ROLES, SYSTEM_PERMISSIONS
from repository.user import UserRepository
from audit.repository import AuditRepository
from exceptions.errors.users import UserNotExistedError


BUILTIN_ROLE_CODES = {item.code for item in DEFAULT_ROLES}
BUILTIN_PERMISSION_CODES = {item.code for item in SYSTEM_PERMISSIONS}


def _fmt_dt(dt) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _serialize_role(role: Roles) -> dict:
    return {
        "uuid": str(role.uuid),
        "space_id": str(role.space_id) if role.space_id else None,
        "scope": role.scope,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "status": role.status,
        "is_builtin": role.code in BUILTIN_ROLE_CODES,
        "created_at": _fmt_dt(role.created_at),
        "updated_at": _fmt_dt(role.updated_at),
    }


def _serialize_permission(permission: Permission) -> dict:
    return {
        "uuid": str(permission.uuid),
        "space_id": str(permission.space_id) if permission.space_id else None,
        "name": permission.name,
        "code": permission.code,
        "description": permission.description,
        "status": permission.status,
        "is_builtin": permission.code in BUILTIN_PERMISSION_CODES,
        "created_at": _fmt_dt(permission.created_at),
        "updated_at": _fmt_dt(permission.updated_at),
    }


class RBACService:

    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.redis = ctx.redis
        self.request = ctx.request
        self.repo = RBACRepository(ctx.db)
        self.user_repo = UserRepository(ctx.db)
        self.activity_log = AuditRepository(ctx.db)

    # ── 角色 CRUD ───────────────────────────────────────

    async def list_roles(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> dict:
        roles = await self.repo.list_roles(space_id, page, page_size, keyword)
        total = await self.repo.count_roles(space_id, keyword)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "roles": [_serialize_role(r) for r in roles],
        }

    async def get_role_detail(self, space_id: UUID, role_id: UUID) -> dict:
        role = await self._get_role_or_raise(space_id, role_id)
        permissions = await self.repo.list_role_permissions(role_id)
        data = _serialize_role(role)
        data["permissions"] = [_serialize_permission(p) for p in permissions]
        return data

    async def create_role(self, space_id: UUID, req: RoleCreateRequest) -> dict:
        if await self.repo.get_role_by_code(req.code):
            raise RoleCodeExistedError
        role = await self.repo.create_role(
            space_id=space_id,
            name=req.name,
            code=req.code,
            scope=req.scope,
            description=req.description,
        )
        return _serialize_role(role)

    async def update_role(
        self,
        space_id: UUID,
        role_id: UUID,
        req: RoleUpdateRequest,
    ) -> dict:
        role = await self._get_role_or_raise(space_id, role_id)
        if role.space_id is None and role.code in BUILTIN_ROLE_CODES:
            # 内置角色仅允许改 status 之外字段也允许，但禁止改 code（这里 schema 本身就不接受 code）
            pass
        updates = req.model_dump(exclude_none=True)
        role = await self.repo.update_role(role, **updates)
        return _serialize_role(role)

    async def delete_role(self, space_id: UUID, role_id: UUID) -> None:
        role = await self._get_role_or_raise(space_id, role_id)
        if role.code in BUILTIN_ROLE_CODES:
            raise BuiltinRoleProtectedError
        # 软删除前先取出受影响的 user_id，便于刷新缓存
        affected_user_ids = await self.repo.get_user_ids_by_role(role_id)
        await self.repo.soft_delete_role(role)
        for uid in affected_user_ids:
            await refresh_user_permissions(self.redis, uid, self.db)

    # ── 权限 CRUD ───────────────────────────────────────

    async def list_permissions(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> dict:
        permissions = await self.repo.list_permissions(space_id, page, page_size, keyword)
        total = await self.repo.count_permissions(space_id, keyword)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "permissions": [_serialize_permission(p) for p in permissions],
        }

    async def get_permission_detail(self, space_id: UUID, permission_id: UUID) -> dict:
        permission = await self._get_permission_or_raise(space_id, permission_id)
        return _serialize_permission(permission)

    async def create_permission(self, space_id: UUID, req: PermissionCreateRequest) -> dict:
        if await self.repo.get_permission_by_code(req.code):
            raise PermissionCodeExistedError
        permission = await self.repo.create_permission(
            space_id=space_id,
            name=req.name,
            code=req.code,
            description=req.description,
        )
        return _serialize_permission(permission)

    async def update_permission(
        self,
        space_id: UUID,
        permission_id: UUID,
        req: PermissionUpdateRequest,
    ) -> dict:
        permission = await self._get_permission_or_raise(space_id, permission_id)
        updates = req.model_dump(exclude_none=True)
        permission = await self.repo.update_permission(permission, **updates)
        return _serialize_permission(permission)

    async def delete_permission(self, space_id: UUID, permission_id: UUID) -> None:
        permission = await self._get_permission_or_raise(space_id, permission_id)
        if permission.code in BUILTIN_PERMISSION_CODES:
            raise BuiltinPermissionProtectedError
        await self.repo.soft_delete_permission(permission)

    # ── 角色-权限绑定 ───────────────────────────────────

    async def list_role_permissions(self, space_id: UUID, role_id: UUID) -> list[dict]:
        await self._get_role_or_raise(space_id, role_id)
        permissions = await self.repo.list_role_permissions(role_id)
        return [_serialize_permission(p) for p in permissions]

    async def bind_role_permissions(
        self,
        space_id: UUID,
        role_id: UUID,
        req: RolePermissionBindRequest,
    ) -> dict:
        await self._get_role_or_raise(space_id, role_id)
        # 校验权限存在性 & 可见性
        valid_permissions = await self.repo.get_permissions_by_ids(space_id, req.permission_ids)
        valid_ids = {p.uuid for p in valid_permissions}
        missing = [pid for pid in req.permission_ids if pid not in valid_ids]
        if missing:
            raise PermissionNotFoundError
        added = await self.repo.bind_role_permissions(role_id, req.permission_ids)
        # 刷新该角色下所有用户的权限缓存
        affected_user_ids = await self.repo.get_user_ids_by_role(role_id)
        for uid in affected_user_ids:
            await refresh_user_permissions(self.redis, uid, self.db)
        return {"added": added}

    async def unbind_role_permissions(
        self,
        space_id: UUID,
        role_id: UUID,
        req: RolePermissionUnbindRequest,
    ) -> dict:
        await self._get_role_or_raise(space_id, role_id)
        affected_user_ids = await self.repo.get_user_ids_by_role(role_id)
        removed = await self.repo.unbind_role_permissions(role_id, req.permission_ids)
        for uid in affected_user_ids:
            await refresh_user_permissions(self.redis, uid, self.db)
        return {"removed": removed}

    # ── 用户-角色绑定 ───────────────────────────────────

    async def list_user_roles(self, space_id: UUID, user_id: UUID) -> list[dict]:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        roles = await self.repo.list_user_roles(user_id)
        return [_serialize_role(r) for r in roles]

    async def add_members(self, space_id: UUID, role_id: UUID, req: GroupMemberAddRequest) -> dict:
        await self._get_role_or_raise(space_id, role_id)

        for user_id in req.user_ids:
            user = await self.user_repo.get(user_id)
            if not user or user.space_id != space_id:
                raise UserNotExistedError

        added = await self.repo.add_role_members(role_id, req.user_ids)

        for user_id in req.user_ids:
            await refresh_user_permissions(self.redis, user_id, self.db)

        return {"added": added}

    async def remove_members(self, space_id: UUID, role_id: UUID, req: GroupMemberRemoveRequest) -> dict:
        await self._get_role_or_raise(space_id, role_id)

        for user_id in req.user_ids:
            user = await self.user_repo.get(user_id)
            if not user or user.space_id != space_id:
                raise UserNotExistedError

        removed = await self.repo.remove_role_members(role_id, req.user_ids)

        for user_id in req.user_ids:
            await refresh_user_permissions(self.redis, user_id, self.db)

        return {"removed": removed}

    async def add_user_roles(
        self,
        space_id: UUID,
        user_id: UUID,
        req: UserRoleBindRequest,
    ) -> dict:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        valid_roles = await self.repo.get_roles_by_ids(space_id, req.role_ids)
        valid_ids = {r.uuid for r in valid_roles}
        missing = [rid for rid in req.role_ids if rid not in valid_ids]
        if missing:
            raise RoleNotFoundError
        added = await self.repo.add_user_roles(user_id, req.role_ids)
        await refresh_user_permissions(self.redis, user_id, self.db)
        return {"added": added}

    async def remove_user_roles(
        self,
        space_id: UUID,
        user_id: UUID,
        req: UserRoleUnbindRequest,
    ) -> dict:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        removed = await self.repo.remove_user_roles(user_id, req.role_ids)
        await refresh_user_permissions(self.redis, user_id, self.db)
        return {"removed": removed}

    # ── 内部方法 ────────────────────────────────────────

    async def _get_role_or_raise(self, space_id: UUID, role_id: UUID) -> Roles:
        role = await self.repo.get_role(space_id, role_id)
        if not role:
            raise RoleNotFoundError
        return role

    async def _get_permission_or_raise(self, space_id: UUID, permission_id: UUID) -> Permission:
        permission = await self.repo.get_permission(space_id, permission_id)
        if not permission:
            raise PermissionNotFoundError
        return permission
