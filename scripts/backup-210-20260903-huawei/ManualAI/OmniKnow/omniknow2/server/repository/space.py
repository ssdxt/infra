from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models.rag import Space, User, KnowledgeBase, ChatResource
from exceptions.errors.resource import SpaceNotExistedError
from schemas.kbase import KbaseStatus
from schemas.user import CurrentUser


class SpaceRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _query(self, uuid: UUID) -> Space | None:
        result = await self.session.execute(
            select(Space).where(Space.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def get(self, uuid: UUID) -> Space | None:
        """根据UUID查询空间"""
        result = await self._query(uuid)
        if not result:
            raise SpaceNotExistedError
        return result

    async def check_exists(self, uuid: UUID) -> bool:
        """检查空间是否存在"""
        result = await self._query(uuid)
        return result is not None

    async def create(self, name, logo, description, owner: UUID, code: str) -> Space:
        orm_obj = Space(
            name=name,
            owner=owner,
            code=code,
            logo=logo,
            description=description
        )

        self.session.add(orm_obj)
        await self.session.flush()  # 获取自增 ID
        # await self.session.commit()
        # await self.session.refresh(orm_obj)

        return orm_obj

    async def exists_by_name(self, user: CurrentUser, name: str) -> bool:
        """判断该用户下是否存在同名空间"""
        res = await self.session.execute(
            select(Space.uuid).where(Space.name == name, Space.owner == user.uuid)
        )
        return res.scalar_one_or_none() is not None

    async def get_by_code(self, code: str) -> Space | None:
        """根据空间code查询空间"""
        result = await self.session.execute(
            select(Space).where(Space.code == code)
        )
        space_orm = result.scalar_one_or_none()
        return space_orm

    async def get_spaces_by_user(self, user_id: UUID):
        """获取用户所属空间（一对一，返回列表以保持接口兼容）"""
        user = await self.session.execute(
            select(User).where(User.uuid == user_id)
        )
        user_obj = user.scalar_one_or_none()
        if not user_obj or not user_obj.space_id:
            return []
        result = await self.session.execute(
            select(Space).where(Space.uuid == user_obj.space_id)
        )
        space = result.scalar_one_or_none()
        return [space] if space else []

    async def get_space_partner_list(self, space_uuid: UUID):
        """获取空间内所有用户列表"""
        stmt = select(User).where(User.space_id == space_uuid)
        result = await self.session.execute(stmt)
        users = result.scalars().all()
        return users

    async def get_own_spaces(self, user_id: UUID):
        """获取用户拥有的空间列表"""
        result = await self.session.execute(
            select(Space).where(Space.owner == user_id)
        )
        spaces = result.scalars().all()
        return spaces

    async def add_user_to_space(self, space: Space, user: User):
        """添加用户到空间（直接设置 User 的 space_id 和 space_role）"""
        user.space_id = space.uuid
        user.space_role = "owner" if space.owner == user.uuid else "member"
        self.session.add(user)
        await self.session.flush()
        return True

    async def update_space(self, space_uuid, space_update_info):
        """更新空间信息"""
        for key, value in space_update_info.model_dump(exclude={"space_uuid"}).items():
            setattr(space_uuid, key, value)
            self.session.add(space_uuid)
        await self.session.commit()
        await self.session.refresh(space_uuid)
        return space_uuid

    async def get_space_member(self, space_id: UUID, user_id: UUID) -> User | None:
        """查询空间成员（通过 User 表的 space_id 判断）"""
        stmt = (
            select(User)
            .where(
                User.uuid == user_id,
                User.space_id == space_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def remove_member(self, space_id: UUID, user_id: UUID) -> bool:
        """移除空间成员（清空 User 的 space_id 和 space_role）"""
        member = await self.get_space_member(space_id, user_id)
        if not member:
            return False
        member.space_id = None
        member.space_role = None
        self.session.add(member)
        await self.session.commit()
        return True

    async def update_member_role(self, space_id: UUID, user_id: UUID, new_role: str) -> bool:
        """更新空间成员角色"""
        member = await self.get_space_member(space_id, user_id)
        if not member:
            return False
        member.space_role = new_role
        self.session.add(member)
        await self.session.commit()
        return True

    async def delete_kbase(self, space_id: UUID, kbase_id: UUID):
        """删除空间下的知识库"""
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.uuid == kbase_id,
                KnowledgeBase.status != KbaseStatus.deleted
            )
        )
        result = await self.session.execute(stmt)
        kb_orm = result.scalar_one_or_none()
        kb_orm.status = KbaseStatus.deleted
        await self.session.flush()
        # await self.session.commit()
        return True

    async def get_space_chat_resource_list(self, space_id: UUID):
        """获取空间下的聊天资源列表（知识库列表）"""
        stmt = (
            select(ChatResource)
            .where(
                ChatResource.space_id == space_id,
            )
        )
        result = await self.session.execute(stmt)
        chat_res_list = result.scalars().all()
        return chat_res_list