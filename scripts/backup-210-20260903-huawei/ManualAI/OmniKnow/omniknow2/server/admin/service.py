import os
from uuid import UUID
from typing import Optional

from core.dependencies import RequestContext
from core.permission_cache import invalidate_user_permissions, refresh_user_permissions
from admin.repository import ResourceGroupRepository
from admin.error import ResourceGroupNotFoundError, ResourceGroupNameExistedError
from admin.schema import (
    ResourceGroupCreateRequest,
    ResourceGroupUpdateRequest,
    GroupMemberAddRequest,
    GroupMemberRemoveRequest,
    GroupPermissionBindRequest,
    GroupPermissionUnbindRequest,
    AdminUserStatusRequest,
    AdminUserRoleRequest, AdminUserCreateRequest,
)
from repository.user import UserRepository
from audit.repository import AuditRepository
from exceptions.errors.users import UserNotExistedError, UserExistedError
from utils import encode_password, base64_to_str
from utils.password_validator import validate_password_strength


class ResourceGroupService:

    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.repo = ResourceGroupRepository(ctx.db)
        self.user_repo = UserRepository(ctx.db)

    # ── 资源用户组 CRUD ─────────────────────────────────

    async def list_groups(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> dict:
        groups = await self.repo.list_groups(space_id, page, page_size, keyword)
        total = await self.repo.count_groups(space_id, keyword)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "groups": [
                {
                    "uuid": str(g.uuid),
                    "name": g.name,
                    "description": g.description,
                    "status": g.status,
                    "member_count": await self.repo.count_members(g.uuid),
                    "created_at": g.created_at.strftime("%Y-%m-%d %H:%M:%S") if g.created_at else None,
                    "updated_at": g.updated_at.strftime("%Y-%m-%d %H:%M:%S") if g.updated_at else None,
                }
                for g in groups
            ],
        }

    async def get_group_detail(self, space_id: UUID, group_uuid: UUID) -> dict:
        group = await self._get_group_or_raise(space_id, group_uuid)
        member_count = await self.repo.count_members(group.uuid)
        permissions = await self.repo.list_group_permissions(space_id, group.uuid)
        return {
            "uuid": str(group.uuid),
            "name": group.name,
            "description": group.description,
            "status": group.status,
            "member_count": member_count,
            "permissions": [
                {
                    "id": acl.id,
                    "resource_type": acl.resource_type,
                    "resource_id": str(acl.resource_id),
                    "role": acl.role,
                    "effect": acl.effect,
                    "created_at": acl.created_at.strftime("%Y-%m-%d %H:%M:%S") if acl.created_at else None,
                }
                for acl in permissions
            ],
            "created_at": group.created_at.strftime("%Y-%m-%d %H:%M:%S") if group.created_at else None,
            "updated_at": group.updated_at.strftime("%Y-%m-%d %H:%M:%S") if group.updated_at else None,
        }

    async def create_group(self, space_id: UUID, req: ResourceGroupCreateRequest) -> dict:
        existing = await self.repo.get_group_by_name(space_id, req.name)
        if existing:
            raise ResourceGroupNameExistedError
        group = await self.repo.create_group(space_id, req.name, req.description)
        return {
            "uuid": str(group.uuid),
            "name": group.name,
            "description": group.description,
            "status": group.status,
        }

    async def update_group(self, space_id: UUID, group_uuid: UUID, req: ResourceGroupUpdateRequest) -> dict:
        group = await self._get_group_or_raise(space_id, group_uuid)
        # 名称唯一性校验
        if req.name and req.name != group.name:
            existing = await self.repo.get_group_by_name(space_id, req.name)
            if existing:
                raise ResourceGroupNameExistedError
        updates = req.model_dump(exclude_none=True)
        group = await self.repo.update_group(group, **updates)
        return {
            "uuid": str(group.uuid),
            "name": group.name,
            "description": group.description,
            "status": group.status,
        }

    async def delete_group(self, space_id: UUID, group_uuid: UUID) -> None:
        group = await self._get_group_or_raise(space_id, group_uuid)
        # 级联清理：成员关系 + ACL 记录
        await self.repo.delete_group_members(group.uuid)
        await self.repo.delete_group_acls(group.uuid)
        await self.repo.delete_group(group)

    # ── 组成员管理 ──────────────────────────────────────

    async def list_members(
        self,
        space_id: UUID,
        group_uuid: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        await self._get_group_or_raise(space_id, group_uuid)
        members = await self.repo.list_members(group_uuid, page, page_size)
        total = await self.repo.count_members(group_uuid)

        # 补充用户信息
        member_list = []
        for m in members:
            user = await self.user_repo.get(m.user_id)
            member_list.append({
                "user_id": str(m.user_id),
                "user_name": user.name if user else None,
                "user_account": user.account if user else None,
                "joined_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else None,
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "members": member_list,
        }

    async def add_members(
        self,
        space_id: UUID,
        group_uuid: UUID,
        req: GroupMemberAddRequest,
    ) -> dict:
        await self._get_group_or_raise(space_id, group_uuid)
        # 校验用户存在性
        for user_id in req.user_ids:
            user = await self.user_repo.get(user_id)
            if not user:
                raise UserNotExistedError
        added = await self.repo.add_members(group_uuid, req.user_ids)
        return {"added": added}

    async def remove_members(
        self,
        space_id: UUID,
        group_uuid: UUID,
        req: GroupMemberRemoveRequest,
    ) -> dict:
        await self._get_group_or_raise(space_id, group_uuid)
        removed = await self.repo.remove_members(group_uuid, req.user_ids)
        return {"removed": removed}

    # ── 组权限绑定 ──────────────────────────────────────

    async def list_group_permissions(self, space_id: UUID, group_uuid: UUID) -> list:
        await self._get_group_or_raise(space_id, group_uuid)
        permissions = await self.repo.list_group_permissions(space_id, group_uuid)
        return [
            {
                "id": acl.id,
                "resource_type": acl.resource_type,
                "resource_id": str(acl.resource_id),
                "role": acl.role,
                "effect": acl.effect,
                "created_at": acl.created_at.strftime("%Y-%m-%d %H:%M:%S") if acl.created_at else None,
            }
            for acl in permissions
        ]

    async def list_permissions(
        self,
        space_id: UUID,
    ):
        permissions = await self.repo.get_resource_acl_entries(space_id)
        return [
            {
                "id": acl.id,
                "subject_id": str(acl.subject_id),
                "subject_type": acl.subject_type,
                "resource_type": acl.resource_type,
                "resource_id": str(acl.resource_id),
                "role": acl.role,
                "effect": acl.effect,
                "created_at": acl.created_at.strftime("%Y-%m-%d %H:%M:%S") if acl.created_at else None,
            }
            for acl in permissions
        ]

    async def bind_permission(
        self,
        space_id: UUID,
        group_uuid: UUID,
        req: GroupPermissionBindRequest,
    ) -> dict:
        await self._get_group_or_raise(space_id, group_uuid)
        acl = await self.repo.bind_permission(
            space_id=space_id,
            group_uuid=group_uuid,
            resource_type=req.resource_type,
            resource_id=req.resource_id,
            role=req.role,
            effect=req.effect,
        )
        return {
            "id": acl.id,
            "resource_type": acl.resource_type,
            "resource_id": str(acl.resource_id),
            "role": acl.role,
            "effect": acl.effect,
        }

    async def unbind_permission(
        self,
        space_id: UUID,
        group_uuid: UUID,
        req: GroupPermissionUnbindRequest,
    ) -> None:
        await self._get_group_or_raise(space_id, group_uuid)
        await self.repo.unbind_permission(
            space_id=space_id,
            group_uuid=group_uuid,
            resource_type=req.resource_type,
            resource_id=req.resource_id,
        )

    # ── 内部方法 ────────────────────────────────────────

    async def _get_group_or_raise(self, space_id: UUID, group_uuid: UUID):
        group = await self.repo.get_group(space_id, group_uuid)
        if not group:
            raise ResourceGroupNotFoundError
        return group


class AdminUserService:

    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.redis = ctx.redis
        self.request = ctx.request
        self.user_repo = UserRepository(self.db)
        self.activity_log = AuditRepository(self.db)

    async def list_users(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
    ) -> dict:
        users = await self.user_repo.list_users(space_id, page, page_size, keyword, status)
        total = await self.user_repo.count_users(space_id, keyword, status)
        role_map = {}
        for user in users:
            role_map[user.uuid] = await self.user_repo.get_user_role_codes(user.uuid)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "users": [
                {
                    "space_id": str(user.space_id),
                    "space_role": user.space_role,
                    "uuid": str(user.uuid),
                    "account": user.account,
                    "name": user.name,
                    "status": user.status,
                    "source": user.source,
                    "roles": role_map.get(user.uuid, []),
                    "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for user in users
            ],
        }

    async def get_user_detail(self,space_id: UUID, user_id: UUID) -> dict:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        detail = await self.user_repo.get_detail_by_id(user_id)
        roles = await self.user_repo.get_user_role_codes(user_id)
        return {
            "uuid": str(user.uuid),
            "account": user.account,
            "name": user.name,
            "status": user.status,
            "source": user.source,
            "roles": roles,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            **detail,
        }

    async def create_user(self, space_id: UUID, req: AdminUserCreateRequest) -> dict:
        account = req.account
        name = req.name
        password_b64 = req.password

        existing = await self.user_repo.get_user_by_account(account)
        if existing:
            raise UserExistedError(account)

        password = base64_to_str(password_b64)
        validate_password_strength(password)

        salt = os.urandom(32).hex()
        password_hash = await encode_password(password, salt)
        user = await self.user_repo.create(
            space_id=space_id,
            account=account,
            name=name,
            source="管理员注册",
            salt=salt,
            password_hash=password_hash,
        )
        return {
            "uuid": str(user.uuid),
            "account": user.account,
            "name": user.name,
            "status": user.status,
            "source": user.source,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def update_user_status(self, space_id, user_id: UUID, req: AdminUserStatusRequest) -> bool:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        res = await self.user_repo.update_user_status(user_id, req.status)

        # 封禁时清除权限缓存
        if req.status == 0:
            await invalidate_user_permissions(self.redis, user_id)

        return res

    async def update_user_role(self, space_id: UUID, user_id: UUID, req: AdminUserRoleRequest) -> bool:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        res = await self.user_repo.update_user_role(user_id, req.role_code)

        # 刷新权限缓存
        await refresh_user_permissions(self.redis, user_id, self.db)

        return res

    async def delete_user(self,space_id: UUID, user_id: UUID) -> bool:
        user = await self.user_repo.get(user_id)
        if not user or user.space_id != space_id:
            raise UserNotExistedError
        res = await self.user_repo.update_user_status(user_id, 0)

        await invalidate_user_permissions(self.redis, user_id)

        return res
