from typing import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct

from db.models.rag import User
from db.models.rbac import (Permission,
                           RolePermission,
                           Roles,
                           UserRole)


class RoleRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_permissions_from_db(
            self,
            user_id: UUID,
    ) -> list[str]:
        """根据用户ID获取用户权限列表"""
        stmt = (
            select(distinct(Permission.code))
            .join(RolePermission, RolePermission.permission_id == Permission.uuid)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                Permission.status == 1
            )
        )

        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_role_permissions(self, role_id: str) -> Sequence:
        """根据角色ID获取权限列表"""
        result = await self.session.execute(
            select(Permission.code).join(
                RolePermission,
                Permission.uuid == RolePermission.permission_id
            ).where(
                RolePermission.role_id == role_id
            )
        )
        permissions = result.scalars().all()
        return permissions