from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, distinct, func, delete
from uuid import UUID
from typing import Optional

from db.models.rag import (
    User,
    Department,
    Position,
    Tenant,
    UserDetail
)
from db.models.rbac import (
    Permission,
    RolePermission,
    UserRole,
    Roles
)
class UserRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, uuid: UUID) -> User | None:
        """根据UUID查询用户"""
        result = await self.session.execute(
            select(User).where(User.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def exists_by_account(self, account: str) -> bool:
        """查询账号是否已被占用"""
        result = await self.session.execute(
            select(User).where(User.account == account)
        )
        return result.scalar_one_or_none() is not None

    async def get_by_id(self, user_id: UUID) -> User | None:
        """根据ID 查询用户"""
        result = await self.session.execute(
            select(User).where(User.uuid == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_account(self, user: str) -> User | None:
        """根据账号查询用户"""
        result = await self.session.execute(select(User).where(
            User.account == user)
        )
        row = result.scalar_one_or_none()
        return row

    async def create(self, *, space_id: UUID, name: str, account: str, salt: str, source: str, password_hash: str, role: int = 2, status: int = 1) -> User:
        """创建用户"""
        orm_obj = User(
            space_id=space_id,
            name=name,
            account=account,
            role=role,
            status=status,
            password=password_hash,
            salt=salt,
            source=source,
        )

        self.session.add(orm_obj)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(orm_obj)
        return orm_obj

    async def update_deatil(self, user: User, detail: dict):
        """更新用户详细信息"""
        res = await self.session.execute(select(UserDetail).where(UserDetail.user_id == user.uuid))
        user_detail = res.scalar_one_or_none()

        if user_detail is None:
            user_detail = UserDetail(
                user_id=user.uuid,
                **detail
            )
            self.session.add(user_detail)
        else:
            for key, value in detail.items():
                setattr(user_detail, key, value)
                self.session.add(user_detail)

        # 如果需要修改用户名，则同步更新 User 表中的 name 字段
        if detail.get("name"):
            user.name = detail["name"]
            self.session.add(user)

        await self.session.flush()

        # await self.session.commit()
        # await self.session.refresh(user_detail)
        # return True

    async def update_password(self, user: User, secret: str):
        """更新用户密码"""
        user.password = secret
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return True

    async def get_detail_by_id(self, user_id: UUID) -> dict:
        """获取用户详细信息"""
        res = await self.session.execute(select(UserDetail.user_id,
                                                UserDetail.ent_id,
                                                UserDetail.email,
                                                UserDetail.department_id,
                                                UserDetail.position_id,
                                                UserDetail.birthday,
                                                UserDetail.sex,
                                                UserDetail.phone).
                                         where(UserDetail.user_id == user_id))
        row = res.all()
        if row is None:
            return {}
        else:
            stmt = (
                select(
                    # User.uuid,
                    # User.name,
                    Department.name.label("department_name"),
                    Position.name.label("position_name"),
                    Tenant.name.label("tenant_name"),
                )
                .select_from(User)
                .outerjoin(UserDetail, UserDetail.user_id == User.uuid)
                .outerjoin(Department, Department.uuid == UserDetail.department_id)
                .outerjoin(Position, Position.uuid == UserDetail.position_id)
                .outerjoin(Tenant, Tenant.uuid == UserDetail.ent_id)
                .where(User.uuid == user_id)
            )

            result = await self.session.execute(stmt)
            data = result.mappings().first()

            data = dict(data)

        return data

    async def add_default_role_to_user(self, user: User):
        """为新用户分配默认角色"""
        res = await self.session.execute(
            select(Roles.uuid).where(Roles.code == "user", Roles.scope == "global")
        )
        role_id = res.scalar_one()
        if role_id is None:
            raise ValueError("默认用户角色不存在，请检查数据库配置。")

        user_role = UserRole(
            user_id=user.uuid,
            role_id=role_id
        )
        self.session.add(user_role)
        # await self.session.commit()
        # return True

    async def is_superadmin(self, user_id: UUID) -> bool:
        """判断用户是否为超级管理员"""
        stmt = (
            select(UserRole.role_id)
            .join(Roles, Roles.uuid == UserRole.role_id)
            .where(
                UserRole.user_id == user_id,
                Roles.code == "superadmin",
                Roles.scope == "global"
            )
        )

        result = await self.session.execute(stmt)
        role = result.scalar_one_or_none()
        return role is not None

    async def count_all_users(self, space_id) -> int:
        """统计空间中所有用户数量"""
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.space_id == space_id)
        )
        return result.scalar()

    async def list_users(
        self,
        space_id: UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
    ) -> list[User]:
        """分页查询用户列表"""
        stmt = select(User)
        if keyword:
            stmt = stmt.where(
                or_(
                    User.account.contains(keyword),
                    User.name.contains(keyword),
                ),
                User.space_id == space_id
            )
        if status is not None:
            stmt = stmt.where(User.status == status, User.space_id == space_id)
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_users(
        self,
        space_id: UUID,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
    ) -> int:
        """统计用户总数"""
        stmt = select(func.count()).select_from(User)
        if keyword:
            stmt = stmt.where(
                or_(
                    User.account.contains(keyword),
                    User.name.contains(keyword),
                ),
                User.space_id == space_id
            )
        if status is not None:
            stmt = stmt.where(User.status == status, User.space_id == space_id)
        result = await self.session.execute(stmt)
        return result.scalar()

    async def update_user_status(self, user_id: UUID, new_status: int) -> bool:
        """更新用户状态"""
        user = await self.get(user_id)
        if not user:
            return False
        user.status = new_status
        self.session.add(user)
        await self.session.commit()
        return True

    async def update_user_role(self, user_id: UUID, role_code: str) -> bool:
        """更新用户 RBAC 角色（替换所有现有角色）"""
        # 查找目标角色
        res = await self.session.execute(
            select(Roles.uuid).where(Roles.code == role_code, Roles.scope == "global")
        )
        role_id = res.scalar_one_or_none()
        if role_id is None:
            raise ValueError(f"角色 '{role_code}' 不存在")

        # 删除现有角色关联
        await self.session.execute(
            delete(UserRole).where(UserRole.user_id == user_id)
        )
        # 创建新角色关联
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(user_role)
        await self.session.commit()
        return True

    async def get_user_role_codes(self, user_id: UUID) -> list[str]:
        """查询用户所有角色 code"""
        stmt = (
            select(Roles.code)
            .join(UserRole, UserRole.role_id == Roles.uuid)
            .where(UserRole.user_id == user_id, Roles.status == 1)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

