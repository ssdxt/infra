"""
资源管理统一入口（核心模块）。

薄访问层，只负责：
  - ACL 鉴权守卫（对外方法会自动执行 ACL 检查）
  - ACL 生命周期（grant_owner / 资源级删除透传）

对外方法需要用户上下文（通过 `ResourceManager(ctx)` 构造）；
系统回调场景使用 `ResourceManager.internal(session)` 工厂创建无用户实例，跳过鉴权。

注意：所有业务流程（批量上传、Markdown upsert、资源删除/归档级联、DTO 组装、
解析回调后处理）已迁移至 `services/document.py` 的 `DocumentService`；
所有 OSS I/O 逻辑已迁移至 `oss/service.py` 的 `OSSService`；
所有 Milvus 调用已迁移至 `vector/milvus.py` 的 `MilvusClient`。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.acl.acl import ACL
from core.dependencies import RequestContext
from core.acl.schema import Action


class ResourceGuard:
    """资源鉴权守卫与 ACL 生命周期。"""

    def __init__(self, ctx: RequestContext):
        self.session = ctx.db
        self.user = ctx.user
        self.acl = ACL(ctx.db)

    @classmethod
    def internal(cls, session: AsyncSession, redis=None) -> "ResourceGuard":
        """创建无用户上下文的内部实例，用于系统回调（跳过鉴权）。"""
        instance = cls.__new__(cls)
        instance.session = session
        instance.user = None
        instance.acl = ACL(session)
        return instance

    # ─── 鉴权守卫 ─────────────────────────────────────────────────

    async def _check(
        self,
        space_id: UUID,
        resource_type: str,
        resource_id: UUID,
        action: Action,
    ) -> None:
        """统一鉴权入口。内部实例（user=None）自动跳过。"""
        if self.user is None:
            return
        await self.acl.check_acl(
            user_id=self.user.uuid,
            space_id=space_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )

    async def check_kbase_access(
        self, space_id: UUID, kbase_id: UUID, action: Action
    ) -> None:
        """kbase 级鉴权，供业务服务在操作前调用。"""
        await self._check(space_id, "kbase", kbase_id, action)

    # ─── ACL 生命周期 ─────────────────────────────────────────────

    async def grant_owner(
        self, space_id: UUID, resource_type: str, resource_id: UUID
    ) -> None:
        """创建资源时自动为当前用户设置 owner ACL。"""
        if self.user is None:
            return
        await self.acl.add_user_acl(
            space_id=space_id,
            user_id=self.user.uuid,
            resource_type=resource_type,
            resource_id=resource_id,
            role="owner",
        )
