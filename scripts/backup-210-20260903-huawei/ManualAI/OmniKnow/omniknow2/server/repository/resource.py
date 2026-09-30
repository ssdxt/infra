from uuid import UUID

from sqlalchemy import exists, select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.acl import ResourceACL
from db.models.rag import Resource, User
from exceptions.errors.resource import ResourceNotExistedError
from core.acl.schema import RESOURCE_ROLE_ORDER, SPACE_ROLE_ORDER, ResourceStatus


class ResRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def has_resource_deny(
        self,
        *,
        user_id: UUID,
        space_id: UUID,
        resource_type: str,
        resource_id: UUID,
        group_ids: list[UUID] | None = None,
    ) -> bool:

        subject_cond = [
            and_(ResourceACL.subject_type == "user", ResourceACL.subject_id == user_id)
        ]
        if group_ids:
            subject_cond.append(
                and_(ResourceACL.subject_type == "group", ResourceACL.subject_id.in_(group_ids))
            )

        stmt = select(
            exists().where(
                ResourceACL.space_id == space_id,
                or_(*subject_cond),
                ResourceACL.resource_type == resource_type,
                ResourceACL.resource_id == resource_id,
                ResourceACL.effect == "deny",
                ResourceACL.status == "active",
            )
        )
        res = await self.db.execute(stmt)
        flag = res.scalar()
        return flag

    async def has_resource_allow(
        self,
        *,
        user_id: UUID,
        space_id: UUID,
        resource_type: str,
        resource_id: UUID,
        min_role: str,
        group_ids: list[UUID] | None = None,
    ) -> bool:

        subject_cond = [
            and_(ResourceACL.subject_type == "user", ResourceACL.subject_id == user_id)
        ]
        if group_ids:
            subject_cond.append(
                and_(ResourceACL.subject_type == "group", ResourceACL.subject_id.in_(group_ids))
            )

        stmt = (
            select(ResourceACL.role)
            .where(
                ResourceACL.space_id == space_id,
                or_(*subject_cond),
                ResourceACL.resource_type == resource_type,
                ResourceACL.resource_id == resource_id,
                ResourceACL.effect == "allow",
                ResourceACL.status == "active",
            )
        )

        res = await self.db.execute(stmt)
        roles = [row[0] for row in res.all()]
        if not roles:
            return False

        # 取最高角色进行比较
        max_role_order = max(RESOURCE_ROLE_ORDER[r] for r in roles)
        return max_role_order >= RESOURCE_ROLE_ORDER[min_role]


    async def check_space_role(
            self,
            *,
            user_id: UUID,
            space_id: UUID,
            min_role: str,
        ) -> bool:

        stmt = (
            select(User.space_role)
            .where(
                User.uuid == user_id,
                User.space_id == space_id,
            )
            .limit(1)
        )

        res = await self.db.execute(stmt)
        role = res.scalar_one_or_none()
        if not role:
            return False
        user_role = SPACE_ROLE_ORDER[role]
        required_role = SPACE_ROLE_ORDER[min_role]
        return user_role >= required_role

    async def add_resource_acl(self, space_id: UUID, subject_type: str, subject_id: UUID, resource_type, resource_id, role, effect="allow") -> ResourceACL:
        """添加资源ACL记录"""
        orm_obj = ResourceACL(
            space_id=space_id,
            subject_type=subject_type,
            subject_id=subject_id,
            resource_type=resource_type,
            resource_id=resource_id,
            role=role,
            effect=effect,
            status="active",
        )
        self.db.add(orm_obj)
        await self.db.flush()  # 获取自增 ID
        # await self.db.commit()
        # await self.db.refresh(orm_obj)
        return orm_obj

    async def delete_acls(
        self,
        *,
        space_id: UUID,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        """删除与资源相关的ACL记录"""
        await self.db.execute(
            ResourceACL.__table__.delete().where(
                ResourceACL.space_id == space_id,
                ResourceACL.resource_type == resource_type,
                ResourceACL.resource_id == resource_id,
            )
        )
        # await self.db.commit()
        await self.db.flush()

    async def delete_resource(self, space_id: UUID, kbase_id: UUID, resource_id: UUID) -> bool:
        """删除知识库资源"""
        result = await self.db.execute(
            select(Resource).where(
                Resource.space_id == space_id,
                Resource.kbase_id == kbase_id,
                Resource.uuid == resource_id
            )
        )
        resource = result.scalar_one_or_none()
        if not resource:
            raise ResourceNotExistedError
        else:
            resource.status = ResourceStatus.destroyed
            self.db.add(resource)
            await self.db.flush()
            return True

    async def archive_resource(self, space_id: UUID, kbase_id: UUID, resource_id: UUID) -> bool:
        """归档知识库资源"""
        result = await self.db.execute(
            select(Resource).where(
                Resource.space_id == space_id,
                Resource.kbase_id == kbase_id,
                Resource.uuid == resource_id
            )
        )
        resource = result.scalar_one_or_none()
        if not resource:
            raise ResourceNotExistedError
        else:
            resource.status = ResourceStatus.archived
            self.db.add(resource)
            await self.db.flush()
            return True

    async def check_exist(self, space_id: UUID, kbase_id: UUID, resource_id: UUID) -> bool:
        """检查资源是否存在"""
        result = await self.db.execute(
            select(exists().where(
                Resource.space_id == space_id,
                Resource.kbase_id == kbase_id,
                Resource.uuid == resource_id,
                Resource.status != ResourceStatus.destroyed
            ))
        )
        if not result.scalar():
            raise ResourceNotExistedError
        else:
            return True