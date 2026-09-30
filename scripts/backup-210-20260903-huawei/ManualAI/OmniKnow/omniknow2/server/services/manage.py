from uuid import UUID

from core.acl.acl import ACL
from core.dependencies import RequestContext
from exceptions.errors.resource import SpaceAccessError
from repository import UserRepository, SpaceRepository, KBaseRepository


class ManageService:
    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.user_repo = UserRepository(self.db)
        self.space_repo = SpaceRepository(self.db)
        self.kbase_repo = KBaseRepository(self.db)
        self.acl = ACL(self.db)

    async def get_total_user_count(self, space_id: UUID) -> int:
        """获取总用户数"""
        user_id = self.user.uuid
        space_access = await self.acl.check_space_role(
            space_id=space_id,
            user_id=user_id,
            min_role="admin"
        )
        if not space_access:
            raise SpaceAccessError
        return await self.user_repo.count_all_users(space_id)

    async def get_total_kbase_count(self, space_id: UUID) -> int:
        """获取总空间数"""
        user_id = self.user.uuid
        space_access = await self.acl.check_space_role(
            space_id=space_id,
            user_id=user_id,
            min_role="admin"
        )
        if not space_access:
            raise SpaceAccessError
        return await self.kbase_repo.count_kbases_in_space(space_id)