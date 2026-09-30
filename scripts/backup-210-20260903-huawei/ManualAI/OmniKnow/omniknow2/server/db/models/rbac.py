from .public import BaseModel

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Uuid


class Roles(BaseModel):
    __tablename__ = 'roles'

    space_id = Column(Uuid, nullable=True, index=True, comment="所属空间，NULL 表示全局内置")
    scope = Column(String(255), nullable=False, comment="角色作用域")
    name = Column(String(255), nullable=False, comment="角色名称")
    code = Column(String(255), nullable=False, unique=True, comment="角色编码")
    description = Column(Text, comment="角色描述")
    status = Column(Integer, nullable=False, default=1, comment="角色状态")


class UserRole(BaseModel):
    __tablename__ = 'role_user_mapping'

    role_id = Column(Uuid, ForeignKey('roles.uuid'), nullable=False, comment="角色ID")
    user_id = Column(Uuid, ForeignKey('user.uuid'), nullable=False, comment="用户ID")


class Permission(BaseModel):
    __tablename__ = 'permission'

    space_id = Column(Uuid, nullable=True, index=True, comment="所属空间，NULL 表示全局内置")
    name = Column(String(255), nullable=False, comment="权限名称")
    code = Column(String(255), nullable=False, unique=True, comment="权限编码")
    description = Column(Text, comment="权限描述")
    status = Column(Integer, nullable=False, default=1, comment="权限状态")


class RolePermission(BaseModel):
    __tablename__ = 'role_permission_mapping'

    role_id = Column(Uuid, ForeignKey('roles.uuid'), nullable=False, comment="角色ID")
    permission_id = Column(Uuid, ForeignKey('permission.uuid'), nullable=False, comment="权限ID")