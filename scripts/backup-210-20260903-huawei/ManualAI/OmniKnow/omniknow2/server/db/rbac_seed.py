"""
RBAC 基线数据：
1. 显式维护系统级角色与权限注册表
2. 在启动时幂等补齐缺失的角色/权限
3. 校验路由声明的权限码已全部登记到注册表，避免新增接口后漏配
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.rbac import Permission, Roles
from utils.log import logger


@dataclass(frozen=True)
class RoleSeed:
    scope: str
    name: str
    code: str
    description: str


@dataclass(frozen=True)
class PermissionSeed:
    name: str
    code: str
    description: str


DEFAULT_ROLES = [
    RoleSeed(scope="global", name="超级管理员", code="superadmin", description="系统超级管理员，拥有所有权限"),
    RoleSeed(scope="global", name="管理员", code="admin", description="系统管理员"),
    RoleSeed(scope="global", name="普通用户", code="user", description="普通用户，拥有基本权限"),
]


# 注意：public 为虚拟权限，不落库。
SYSTEM_PERMISSIONS = [
    PermissionSeed(name="管理后台查看", code="admin:view", description="查看管理后台统计与概览数据"),
    PermissionSeed(name="管理后台管理", code="admin:manage", description="执行管理后台通用管理操作"),
    PermissionSeed(name="管理员用户管理", code="admin:user:manage", description="管理空间用户、角色与状态"),
    PermissionSeed(name="管理员 ACL 管理", code="admin:acl:manage", description="管理资源用户组与 ACL 权限绑定"),
    PermissionSeed(name="管理员 RBAC 管理", code="admin:rbac:manage", description="管理系统角色、权限及其绑定关系"),
    PermissionSeed(name="日志查看", code="admin:audit:view", description="查看系统日志与审计日志"),
    PermissionSeed(name="会话读取", code="chat:read", description="查看会话列表、详情与历史消息"),
    PermissionSeed(name="会话写入", code="chat:write", description="创建会话、写入消息、修改标题与删除会话"),
    PermissionSeed(name="知识库创建", code="kbase:create", description="创建知识库"),
    PermissionSeed(name="知识库查看", code="kbase:view", description="查看知识库、文档、资源与分块详情"),
    PermissionSeed(name="知识库更新", code="kbase:update", description="更新知识库信息与维护 Markdown 文档"),
    PermissionSeed(name="知识库删除资源", code="kbase:delete", description="删除知识库资源"),
    PermissionSeed(name="知识库上传", code="kbase:upload", description="上传知识库文档、空间图片与 Logo"),
    PermissionSeed(name="知识库解析", code="kbase:parse", description="发起知识库文档解析任务"),
    PermissionSeed(name="空间知识库删除", code="space:kbase:delete", description="从空间维度删除知识库"),
    PermissionSeed(name="考试培训读取", code="training:read", description="查看课程、题目、试卷与考试记录"),
    PermissionSeed(name="考试培训写入", code="training:write", description="创建课程、生成试卷、提交考试结果"),
    PermissionSeed(name="报告读取", code="report:read", description="查看报告列表与详情"),
    PermissionSeed(name="报告写入", code="report:write", description="创建、更新与删除报告")
]


PERMISSION_SCAN_DIRS = (
    "api/endpoints",
    "admin",
    "report",
    "training",
)


def _iter_python_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    files: list[Path] = []

    for relative_dir in PERMISSION_SCAN_DIRS:
        directory = root / relative_dir
        if not directory.exists():
            continue
        files.extend(sorted(directory.rglob("*.py")))

    return files


def collect_route_permission_codes() -> set[str]:
    """
    通过 AST 扫描 route 文件中的 authorize(...) 调用，收集显式声明的权限码。
    """

    permission_codes: set[str] = set()

    for file_path in _iter_python_files():
        module = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue

            if not isinstance(node.func, ast.Name) or node.func.id != "authorize":
                continue

            if not node.args:
                permission_codes.add("public")
                continue

            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                permission_codes.add(first_arg.value)
                continue

            raise RuntimeError(
                f"{file_path} 中的 authorize() 未使用字符串字面量，无法自动校验，请改为显式权限码。"
            )

    return permission_codes


def validate_permission_registry() -> None:
    declared_codes = collect_route_permission_codes() - {"public"}
    registered_codes = {item.code for item in SYSTEM_PERMISSIONS}

    missing_codes = sorted(declared_codes - registered_codes)
    if missing_codes:
        raise RuntimeError(
            "以下权限码已在接口中声明，但未登记到 db/rbac_seed.py 的 SYSTEM_PERMISSIONS 中："
            + ", ".join(missing_codes)
        )


async def sync_default_roles(session: AsyncSession) -> dict[str, Roles]:
    role_codes = [item.code for item in DEFAULT_ROLES]
    result = await session.execute(select(Roles).where(Roles.code.in_(role_codes)))
    existing_roles = {role.code: role for role in result.scalars().all()}

    created_count = 0
    for role_seed in DEFAULT_ROLES:
        if role_seed.code in existing_roles:
            continue

        role = Roles(
            space_id=None,
            scope=role_seed.scope,
            name=role_seed.name,
            code=role_seed.code,
            description=role_seed.description,
        )
        session.add(role)
        existing_roles[role_seed.code] = role
        created_count += 1

    await session.flush()
    logger.info(f"✅ 已同步默认角色，新增 {created_count} 个")
    return existing_roles


async def sync_default_permissions(session: AsyncSession) -> dict[str, Permission]:
    validate_permission_registry()

    permission_codes = [item.code for item in SYSTEM_PERMISSIONS]
    result = await session.execute(select(Permission).where(Permission.code.in_(permission_codes)))
    existing_permissions = {permission.code: permission for permission in result.scalars().all()}

    created_count = 0
    for permission_seed in SYSTEM_PERMISSIONS:
        if permission_seed.code in existing_permissions:
            continue

        permission = Permission(
            space_id=None,
            name=permission_seed.name,
            code=permission_seed.code,
            description=permission_seed.description,
        )
        session.add(permission)
        existing_permissions[permission_seed.code] = permission
        created_count += 1

    await session.flush()
    logger.info(f"✅ 已同步系统权限，新增 {created_count} 个")
    return existing_permissions


async def sync_rbac_baseline(session: AsyncSession) -> tuple[dict[str, Roles], dict[str, Permission]]:
    roles = await sync_default_roles(session)
    permissions = await sync_default_permissions(session)
    return roles, permissions
