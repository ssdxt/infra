from uuid import UUID

from sqlalchemy import select, func, delete, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.rbac import Roles, Permission, UserRole, RolePermission


class RBACRepository:
    """
    管理后台 RBAC 仓储：封装 Roles / Permission / UserRole / RolePermission 的查询。

    space_id 语义：
    - Roles / Permission 通过 (space_id == 当前 space) OR (space_id IS NULL，即全局内置) 限定可见性。
    - 写入时使用调用方传入的 space_id；内置数据 (space_id IS NULL) 由 db/rbac_seed.py 保证。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 角色 CRUD ───────────────────────────────────────

    @staticmethod
    def _role_scope_filter(space_id: UUID):
        return or_(Roles.space_id == space_id, Roles.space_id.is_(None))

    async def list_roles(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> list[Roles]:
        stmt = select(Roles).where(self._role_scope_filter(space_id), Roles.status == 1)
        if keyword:
            stmt = stmt.where(
                or_(
                    Roles.name.ilike(f"%{keyword}%"),
                    Roles.code.ilike(f"%{keyword}%"),
                )
            )
        stmt = stmt.order_by(Roles.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_roles(
        self,
        space_id: UUID,
        keyword: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Roles)
            .where(self._role_scope_filter(space_id), Roles.status == 1)
        )
        if keyword:
            stmt = stmt.where(
                or_(
                    Roles.name.ilike(f"%{keyword}%"),
                    Roles.code.ilike(f"%{keyword}%"),
                )
            )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_role(self, space_id: UUID, role_id: UUID) -> Roles | None:
        stmt = select(Roles).where(
            Roles.uuid == role_id,
            self._role_scope_filter(space_id),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_role_by_code(self, code: str) -> Roles | None:
        stmt = select(Roles).where(Roles.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_role(
        self,
        space_id: UUID,
        name: str,
        code: str,
        scope: str,
        description: str | None = None,
    ) -> Roles:
        role = Roles(
            space_id=space_id,
            name=name,
            code=code,
            scope=scope,
            description=description,
            status=1,
        )
        self.db.add(role)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def update_role(self, role: Roles, **kwargs) -> Roles:
        for key, value in kwargs.items():
            if value is not None:
                setattr(role, key, value)
        self.db.add(role)
        await self.db.flush()
        await self.db.commit()
        return role

    async def soft_delete_role(self, role: Roles) -> None:
        role.status = 0
        self.db.add(role)
        await self.db.flush()
        await self.db.commit()

    # ── 权限 CRUD ───────────────────────────────────────

    @staticmethod
    def _permission_scope_filter(space_id: UUID):
        return or_(Permission.space_id == space_id, Permission.space_id.is_(None))

    async def list_permissions(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> list[Permission]:
        stmt = select(Permission).where(self._permission_scope_filter(space_id))
        if keyword:
            stmt = stmt.where(
                or_(
                    Permission.name.ilike(f"%{keyword}%"),
                    Permission.code.ilike(f"%{keyword}%"),
                )
            )
        stmt = stmt.order_by(Permission.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_permissions(
        self,
        space_id: UUID,
        keyword: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Permission)
            .where(self._permission_scope_filter(space_id))
        )
        if keyword:
            stmt = stmt.where(
                or_(
                    Permission.name.ilike(f"%{keyword}%"),
                    Permission.code.ilike(f"%{keyword}%"),
                )
            )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_permission(self, space_id: UUID, permission_id: UUID) -> Permission | None:
        stmt = select(Permission).where(
            Permission.uuid == permission_id,
            self._permission_scope_filter(space_id),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_permission_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_permission(
        self,
        space_id: UUID,
        name: str,
        code: str,
        description: str | None = None,
    ) -> Permission:
        permission = Permission(
            space_id=space_id,
            name=name,
            code=code,
            description=description,
            status=1,
        )
        self.db.add(permission)
        await self.db.flush()
        await self.db.commit()
        return permission

    async def update_permission(self, permission: Permission, **kwargs) -> Permission:
        for key, value in kwargs.items():
            if value is not None:
                setattr(permission, key, value)
        self.db.add(permission)
        await self.db.flush()
        await self.db.commit()
        return permission

    async def soft_delete_permission(self, permission: Permission) -> None:
        permission.status = 0
        self.db.add(permission)
        await self.db.flush()
        await self.db.commit()

    # ── 角色-权限绑定 ───────────────────────────────────

    async def list_role_permissions(self, role_id: UUID) -> list[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.uuid)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_role_permission_ids(
        self,
        role_id: UUID,
        permission_ids: list[UUID],
    ) -> set[UUID]:
        stmt = select(RolePermission.permission_id).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id.in_(permission_ids),
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def bind_role_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> int:
        existing = await self.get_existing_role_permission_ids(role_id, permission_ids)
        added = 0
        for pid in permission_ids:
            if pid in existing:
                continue
            self.db.add(RolePermission(role_id=role_id, permission_id=pid))
            added += 1
        await self.db.flush()
        await self.db.commit()
        return added

    async def unbind_role_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> int:
        stmt = delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id.in_(permission_ids),
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        await self.db.commit()
        return result.rowcount or 0

    async def get_user_ids_by_role(self, role_id: UUID) -> list[UUID]:
        stmt = select(UserRole.user_id).where(UserRole.role_id == role_id)
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_permissions_by_ids(
        self,
        space_id: UUID,
        permission_ids: list[UUID],
    ) -> list[Permission]:
        stmt = select(Permission).where(
            Permission.uuid.in_(permission_ids),
            self._permission_scope_filter(space_id),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── 用户-角色绑定 ───────────────────────────────────

    async def list_user_roles(self, user_id: UUID) -> list[Roles]:
        stmt = (
            select(Roles)
            .join(UserRole, UserRole.role_id == Roles.uuid)
            .where(UserRole.user_id == user_id)
            .order_by(Roles.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_user_role_ids(
        self,
        user_id: UUID,
        role_ids: list[UUID],
    ) -> set[UUID]:
        stmt = select(UserRole.role_id).where(
            UserRole.user_id == user_id,
            UserRole.role_id.in_(role_ids),
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def add_user_roles(self, user_id: UUID, role_ids: list[UUID]) -> int:
        existing = await self.get_existing_user_role_ids(user_id, role_ids)
        added = 0
        for rid in role_ids:
            if rid in existing:
                continue
            self.db.add(UserRole(user_id=user_id, role_id=rid))
            added += 1
        await self.db.flush()
        await self.db.commit()
        return added

    async def add_role_members(self, role_id: UUID, user_ids: list[UUID]) -> int:
        stmt = select(UserRole.user_id).where(
            UserRole.role_id == role_id,
            UserRole.user_id.in_(user_ids),
        )
        result = await self.db.execute(stmt)
        existing_user_ids = {row[0] for row in result.all()}

        added = 0
        for user_id in user_ids:
            if user_id in existing_user_ids:
                continue
            self.db.add(UserRole(user_id=user_id, role_id=role_id))
            added += 1

        await self.db.flush()
        await self.db.commit()
        return added

    async def remove_role_members(self, role_id: UUID, user_ids: list[UUID]) -> int:
        stmt = delete(UserRole).where(
            UserRole.role_id == role_id,
            UserRole.user_id.in_(user_ids),
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        await self.db.commit()
        return result.rowcount or 0

    async def remove_user_roles(self, user_id: UUID, role_ids: list[UUID]) -> int:
        stmt = delete(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id.in_(role_ids),
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        await self.db.commit()
        return result.rowcount or 0

    async def get_roles_by_ids(
        self,
        space_id: UUID,
        role_ids: list[UUID],
    ) -> list[Roles]:
        stmt = select(Roles).where(
            Roles.uuid.in_(role_ids),
            self._role_scope_filter(space_id),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
