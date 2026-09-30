"""
知识库元数据服务。

职责范围仅限 KnowledgeBase 实体自身的 CRUD 与概览：
  - 创建 / 更新 / 获取 / 概览

所有资源（文档 / Markdown / 分块）相关的业务流程已迁移至
`services/document.py` 的 `DocumentService`。
"""

import time
from typing import Sequence
from uuid import UUID

from core.dependencies import RequestContext
from core.acl.guard import ResourceGuard
from exceptions.errors.resource import (
    CollectionNameExistedError,
    KBaseExistedError,
)
from repository import KBaseRepository, UserRepository
from schemas.kbase import DefaultQuestionCreateSchema
from storage import get_storage
from schemas import Action, KBaseCreateSchema, KBaseUpdateSchema
from utils import hash_md5


class KbaseService:
    def __init__(self, ctx: RequestContext):
        self.session = ctx.db
        self.user = ctx.user
        self.rm = ResourceGuard(ctx)
        self.storage = get_storage()
        self.kbase_repo = KBaseRepository(ctx.db)
        self.user_repo = UserRepository(ctx.db)

    async def _check_kbase_collection_name_unique(
        self, space_id: UUID, collection_name: str
    ) -> None:
        """检查知识库集合名称在空间内是否唯一"""
        if await self.kbase_repo.exists_by_collection_name(space_id, collection_name):
            raise CollectionNameExistedError(collection_name)

    async def get(self, space_id: UUID, kbase_id: UUID):
        """获取知识库信息（带访问控制检查）"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        return await self.kbase_repo.get(space_id, kbase_id)

    async def get_kbase_overview(self, space_id: UUID, kbase_id: UUID) -> dict:
        """获取知识库概览信息"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        kbase = await self.kbase_repo.get(space_id, kbase_id)
        user = await self.user_repo.get_by_id(kbase.user_id)

        if kbase.logo and not kbase.logo.startswith("http"):
            logo = await self.storage.presign(space_id, kbase.logo)
        else:
            logo = kbase.logo

        chat_resource = await self.kbase_repo.get_chat_resources(space_id, kbase.chat_resources)
        return {
            "uuid": kbase.uuid,
            "name": kbase.name,
            "collection_name": kbase.collection_name,
            "description": kbase.description,
            "logo": logo,
            "tag": kbase.tag,
            "public": kbase.public,
            "default_questions": kbase.default_questions,
            "chat_resources": [
                {
                    "uri": res.uri,
                    "title": res.title,
                    "description": res.description,
                    "agent": res.agent
                }
                for res in chat_resource
            ],
            "embed": kbase.embed,
            "status": kbase.status,
            "owner": user.name,
            "owner_id": kbase.user_id,
            "created_at": kbase.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def create_kbase(self, space_id: UUID, kbase_info: KBaseCreateSchema) -> dict:
        """在空间下新增知识库"""
        kbase_name = kbase_info.name
        async with self.session.begin():
            if await self.kbase_repo.exists_by_name(space_id, kbase_name):
                raise KBaseExistedError(kbase_name=kbase_name)

            if kbase_info.collection_name is None or kbase_info.collection_name.strip() == "":
                kbase_info.collection_name = "z_" + hash_md5(
                    f"{space_id}{kbase_name}{time.time()}"
                )

            await self._check_kbase_collection_name_unique(space_id, kbase_info.collection_name)
            kbase = await self.kbase_repo.create(
                space_id,
                kbase_name,
                self.user.uuid,
                kbase_info.description,
                kbase_info.logo,
                kbase_info.public,
                kbase_info.embed,
                kbase_info.collection_name,
                kbase_info.tags,
            )
            await self.rm.grant_owner(space_id, "kbase", kbase.uuid)
            await self.storage.init_kbase_bucket(space_id, kbase.name)

        return {
            "uuid": kbase.uuid,
            "name": kbase.name,
            "collection_name": kbase.collection_name,
            "description": kbase.description,
            "logo": kbase.logo,
            "public": kbase.public,
            "embed": kbase.embed,
        }

    async def update_kbase(
        self, space_id: UUID, kbase_id: UUID, kbase_update_info: KBaseUpdateSchema
    ) -> dict:
        """更新知识库信息"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_edit)

        kbase = await self.kbase_repo.get(space_id, kbase_id)

        if kbase_update_info.name and kbase_update_info.name != kbase.name:
            if await self.kbase_repo.exists_by_name(space_id, kbase_update_info.name):
                raise KBaseExistedError(kbase_name=kbase_update_info.name)
            kbase.name = kbase_update_info.name

        if kbase_update_info.description is not None:
            kbase.description = kbase_update_info.description

        if kbase_update_info.logo is not None:
            kbase.logo = kbase_update_info.logo

        if kbase_update_info.public is not None:
            kbase.public = kbase_update_info.public

        if kbase_update_info.default_questions is not None:
            kbase.default_questions = kbase_update_info.default_questions

        if kbase_update_info.chat_resources is not None:
            kbase.chat_resources = kbase_update_info.chat_resources

        await self.kbase_repo.update_kbase(kbase)

        return {
            "uuid": kbase.uuid,
            "name": kbase.name,
            "description": kbase.description,
            "logo": kbase.logo,
            "public": kbase.public,
            "embed": kbase.embed,
        }

    # async def get_kbase_default_questions(self, space_id: UUID, kbase_id: UUID) -> Sequence:
    #     """获取知识库默认问题列表"""
    #     await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
    #     return await self.kbase_repo.get_default_questions(space_id, kbase_id)
    #
    # async def insert_kbase_default_questions(self, space_id: UUID, kbase_id: UUID, payload: DefaultQuestionCreateSchema) -> list:
    #     """批量插入知识库默认问题"""
    #     await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_edit)
    #
    #     question_list = []
    #     for question in payload.questions:
    #         if not question.content.strip():
    #             raise ValueError("问题内容不能为空")
    #         obj = await self.kbase_repo.insert_questions(space_id, kbase_id, question)
    #         question_list.append({
    #             "uuid": obj.uuid,
    #             "question": obj.question,
    #             "order": obj.order,
    #         })
    #     return question_list
    #
    # async def delete_kbase_default_questions(self, space_id: UUID, kbase_id: UUID, question_id: UUID) -> bool:
    #     """删除知识库默认问题"""
    #     await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_edit)
    #
    #     await self.kbase_repo.delete_questions(space_id, kbase_id, question_id)
    #     return True