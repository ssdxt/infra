from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status, HTTPException

from core.acl.schema import Action, ACTION_POLICY
from repository.resource import ResRepository


class ACL:

    def __init__(self, session: AsyncSession):
        self.res = ResRepository(session)

    async def _get_user_group_ids(self, user_id: UUID) -> list[UUID]:
        from admin.repository import ResourceGroupRepository
        group_repo = ResourceGroupRepository(self.res.db)
        return await group_repo.get_user_group_ids(user_id)

    async def check_acl(self, user_id: UUID, space_id: UUID, resource_type: str, resource_id: UUID, action: Action) -> bool:
        """
        资源权限校验统一入口
        顺序：
        1. deny（ResourceACL，含用户直接 + 所属组）
        2. allow（ResourceACL，含用户直接 + 所属组）
        3. fallback User.space_role
        """

        policy = ACTION_POLICY[action]

        # 查询用户所属的资源用户组
        group_ids = await self._get_user_group_ids(user_id)

        # 1. 显式 deny
        if await self.res.has_resource_deny(
            user_id=user_id,
            space_id=space_id,
            resource_type=resource_type,
            resource_id=resource_id,
            group_ids=group_ids,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限拒绝: 用户被禁止对该资源执行 {action.value} 操作",
            )

        # 2. 显式 allow
        if "resource" in policy:
            if await self.res.has_resource_allow(
                user_id=user_id,
                space_id=space_id,
                resource_type=resource_type,
                resource_id=resource_id,
                min_role=policy["resource"],
                group_ids=group_ids,
            ):
                return True

        # 3. fallback 到 SpaceMember
        if "fallback" in policy:
            res = await self.res.check_space_role(
                user_id=user_id,
                space_id=space_id,
                min_role=policy["fallback"],
            )
            if res:
                return True
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限拒绝: 用户没有权限对该资源执行 {action.value} 操作",
                )
        return True

    async def check_space_role(self, user_id: UUID, space_id: UUID, min_role: str) -> bool:
        return await self.res.check_space_role(
            user_id=user_id,
            space_id=space_id,
            min_role=min_role,
        )

    async def add_user_acl(self, space_id: UUID, user_id: UUID, resource_type, resource_id, role, effect="allow"):
        return await self.res.add_resource_acl(
            space_id=space_id,
            subject_type="user",
            subject_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            role=role,
            effect=effect,
        )

    async def delete_acl(self, space_id, resource_type, resource_id):
        await self.res.delete_acls(space_id=space_id, resource_type=resource_type, resource_id=resource_id)