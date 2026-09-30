from uuid import UUID

from sqlalchemy import select, func, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from admin.model import ResourceGroup, ResourceGroupMember
from db.models.acl import ResourceACL


class ResourceGroupRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 资源用户组 CRUD ─────────────────────────────────

    async def list_groups(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> list[ResourceGroup]:
        stmt = (
            select(ResourceGroup)
            .where(
                ResourceGroup.space_id == space_id,
                ResourceGroup.status != "deleted",
            )
        )
        if keyword:
            stmt = stmt.where(
                or_(
                    ResourceGroup.name.ilike(f"%{keyword}%"),
                    ResourceGroup.description.ilike(f"%{keyword}%"),
                )
            )
        stmt = stmt.order_by(ResourceGroup.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_groups(
        self,
        space_id: UUID,
        keyword: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ResourceGroup)
            .where(
                ResourceGroup.space_id == space_id,
                ResourceGroup.status != "deleted",
            )
        )
        if keyword:
            stmt = stmt.where(
                or_(
                    ResourceGroup.name.ilike(f"%{keyword}%"),
                    ResourceGroup.description.ilike(f"%{keyword}%"),
                )
            )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_group(self, space_id: UUID, group_uuid: UUID) -> ResourceGroup | None:
        stmt = (
            select(ResourceGroup)
            .where(
                ResourceGroup.space_id == space_id,
                ResourceGroup.uuid == group_uuid,
                ResourceGroup.status != "deleted",
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_group_by_name(self, space_id: UUID, name: str) -> ResourceGroup | None:
        stmt = (
            select(ResourceGroup)
            .where(
                ResourceGroup.space_id == space_id,
                ResourceGroup.name == name,
                ResourceGroup.status != "deleted",
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_group(self, space_id: UUID, name: str, description: str | None = None) -> ResourceGroup:
        group = ResourceGroup(
            space_id=space_id,
            name=name,
            description=description,
            status="active",
        )
        self.db.add(group)
        await self.db.flush()
        await self.db.commit()
        return group

    async def update_group(self, group: ResourceGroup, **kwargs) -> ResourceGroup:
        for key, value in kwargs.items():
            if value is not None:
                setattr(group, key, value)
        self.db.add(group)
        await self.db.flush()
        return group

    async def delete_group(self, group: ResourceGroup) -> None:
        group.status = "deleted"
        self.db.add(group)
        await self.db.flush()

    # ── 组成员管理 ──────────────────────────────────────

    async def list_members(
        self,
        group_uuid: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> list[ResourceGroupMember]:
        stmt = (
            select(ResourceGroupMember)
            .where(ResourceGroupMember.group_id == group_uuid)
            .order_by(ResourceGroupMember.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_members(self, group_uuid: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ResourceGroupMember)
            .where(ResourceGroupMember.group_id == group_uuid)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def add_members(self, group_uuid: UUID, user_ids: list[UUID]) -> int:
        added = 0
        for user_id in user_ids:
            # 检查是否已存在
            exists_stmt = (
                select(func.count())
                .select_from(ResourceGroupMember)
                .where(
                    ResourceGroupMember.group_id == group_uuid,
                    ResourceGroupMember.user_id == user_id,
                )
            )
            result = await self.db.execute(exists_stmt)
            if result.scalar():
                continue
            member = ResourceGroupMember(group_id=group_uuid, user_id=user_id)
            self.db.add(member)
            added += 1
        await self.db.flush()
        await self.db.commit()
        return added

    async def remove_members(self, group_uuid: UUID, user_ids: list[UUID]) -> int:
        stmt = (
            delete(ResourceGroupMember)
            .where(
                ResourceGroupMember.group_id == group_uuid,
                ResourceGroupMember.user_id.in_(user_ids),
            )
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    async def delete_group_members(self, group_uuid: UUID) -> None:
        stmt = delete(ResourceGroupMember).where(ResourceGroupMember.group_id == group_uuid)
        await self.db.execute(stmt)
        await self.db.flush()

    # ── 组权限（ResourceACL）操作 ───────────────────────

    async def list_group_permissions(self, space_id: UUID, group_uuid: UUID) -> list[ResourceACL]:
        stmt = (
            select(ResourceACL)
            .where(
                ResourceACL.space_id == space_id,
                ResourceACL.subject_type == "group",
                ResourceACL.subject_id == group_uuid,
                ResourceACL.status == "active",
            )
            .order_by(ResourceACL.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def bind_permission(
        self,
        space_id: UUID,
        group_uuid: UUID,
        resource_type: str,
        resource_id: UUID,
        role: str,
        effect: str = "allow",
    ) -> ResourceACL:
        acl = ResourceACL(
            space_id=space_id,
            subject_type="group",
            subject_id=group_uuid,
            resource_type=resource_type,
            resource_id=resource_id,
            role=role,
            effect=effect,
            status="active",
        )
        self.db.add(acl)
        await self.db.flush()
        await self.db.commit()
        return acl

    async def unbind_permission(
        self,
        space_id: UUID,
        group_uuid: UUID,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        stmt = (
            delete(ResourceACL)
            .where(
                ResourceACL.space_id == space_id,
                ResourceACL.subject_type == "group",
                ResourceACL.subject_id == group_uuid,
                ResourceACL.resource_type == resource_type,
                ResourceACL.resource_id == resource_id,
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def delete_group_acls(self, group_uuid: UUID) -> None:
        stmt = (
            delete(ResourceACL)
            .where(
                ResourceACL.subject_type == "group",
                ResourceACL.subject_id == group_uuid,
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()

    # ── ACL 校验辅助 ───────────────────────────────────

    async def get_user_group_ids(self, user_id: UUID) -> list[UUID]:
        stmt = (
            select(ResourceGroupMember.group_id)
            .join(
                ResourceGroup,
                ResourceGroup.uuid == ResourceGroupMember.group_id,
            )
            .where(
                ResourceGroupMember.user_id == user_id,
                ResourceGroup.status == "active",
            )
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_resource_acl_entries(
        self,
        space_id: UUID,
    ) -> list[ResourceACL]:
        stmt = (
            select(ResourceACL)
            .where(
                ResourceACL.space_id == space_id,
                ResourceACL.status == "active",
            )
            .order_by(ResourceACL.resource_type, ResourceACL.resource_id, ResourceACL.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())