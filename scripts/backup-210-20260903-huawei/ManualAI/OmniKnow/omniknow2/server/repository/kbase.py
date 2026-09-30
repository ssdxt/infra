from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, case

from db.models.rag import KnowledgeBase, Resource, Chunk, DefaultQuestion, ChatResource
from exceptions.errors.resource import KBaseNotExistedError, DocNotExistedError, ChunkNotExistedError
from schemas.kbase import KbaseStatus
from core.acl.schema import ResourceType, ResourceStatus
from utils import logger
from vector import ParserClient


class KBaseRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    # ─── KnowledgeBase CRUD ───────────────────────────────────────────

    async def create(self, space_id, name, user_id, description, logo, public, embed, collection_name, tags):
        orm_obj = KnowledgeBase(
            name=name,
            space_id=space_id,
            logo=logo,
            description=description,
            user_id=user_id,
            public=public,
            embed=embed,
            collection_name=collection_name,
            tag=tags,
        )

        self.session.add(orm_obj)
        await self.session.flush()
        return orm_obj

    async def _query(self, space_id: UUID, uuid: UUID) -> KnowledgeBase | None:
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.uuid == uuid,
                KnowledgeBase.status != KbaseStatus.deleted
            )
        )
        return result.scalar_one_or_none()

    async def get(self, space_id: UUID, uuid: UUID) -> KnowledgeBase | None:
        """根据UUID查询知识库"""
        result = await self._query(space_id, uuid)
        if not result:
            raise KBaseNotExistedError(uuid)
        return result

    async def check_exists(self, space_id: UUID, uuid: UUID) -> bool:
        """检查知识库是否存在"""
        result = await self._query(space_id, uuid)
        return result is not None

    async def get_kbase_by_id(self, space_id: UUID, kbase_id: UUID) -> KnowledgeBase:
        """根据空间ID和知识库ID获取知识库名称"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.uuid == kbase_id
            )
        )
        return result.scalar_one_or_none()

    async def exists_by_name(self, space_id: UUID, name: str) -> bool:
        """判断该用户下是否存在同名知识库"""
        res = await self.session.execute(
            select(KnowledgeBase.uuid).where(
                KnowledgeBase.name == name,
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.status != KbaseStatus.deleted
            )
        )
        return res.scalar_one_or_none() is not None

    async def exists_by_collection_name(self, space_id, collection_name) -> bool:
        """判断该空间下是否存在同名知识库集合"""
        res = await self.session.execute(
            select(KnowledgeBase.uuid).where(
                KnowledgeBase.collection_name == collection_name,
                KnowledgeBase.space_id == space_id)
        )
        return res.scalar_one_or_none() is not None

    async def get_space_kb_list(self, space_id: UUID) -> Sequence[KnowledgeBase]:
        """获取空间知识库列表"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.status != KbaseStatus.deleted
            )
        )
        kb_orm_list = result.scalars().all()
        return kb_orm_list

    async def get_kbase_by_name(self, space_id: UUID, name: str) -> KnowledgeBase | None:
        """根据名称获取知识库"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.name == name
            )
        )
        return result.scalar_one_or_none()

    async def update_kbase(self, kb: KnowledgeBase) -> KnowledgeBase:
        """更新知识库信息"""
        self.session.add(kb)
        await self.session.commit()
        await self.session.refresh(kb)
        return kb

    async def count_kbases_in_space(self, space_id: UUID) -> int:
        """统计空间下知识库数量"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.space_id == space_id
            )
        )
        kb_orm_list = result.scalars().all()
        return len(kb_orm_list)

    # ─── Resource CRUD ────────────────────────────────────────────────

    async def add_resource(self, space_id: UUID,
                           kbase_id: UUID,
                           name: str,
                           resource_type: str,
                           owner: UUID,
                           path: str = None,
                           link=None,
                           _object=None,
                           uuid: UUID = None,
                           size: int = None,
                           md5: str = None,
                           description: str = None,
                           # 文档类型专属字段
                           content: str = None,
                           file_type: str = None,
                           chunk_size: int = 0,
                           status: str = None,
                           source: str = None,
                           identification_method: str = None,
                           block_strategy: str = None,
                           index_strategy: str = None,
                           ) -> Resource:
        """添加知识库资源（通用 + 文档专属字段）"""
        orm_obj = Resource(
            uuid=uuid,
            space_id=space_id,
            kbase_id=kbase_id,
            name=name,
            type=resource_type,
            path=path,
            size=size,
            md5=md5,
            link=link,
            object=_object,
            description=description,
            status=status,
            owner_id=owner,
            # 文档专属
            content=content,
            file_type=file_type,
            chunk_size=chunk_size,
            source=source,
            identification_method=identification_method,
            block_strategy=block_strategy,
            index_strategy=index_strategy,
        )
        self.session.add(orm_obj)
        await self.session.flush()
        return orm_obj

    async def get_resources(
        self, space_id: UUID, kbase_id: UUID, resource_type: ResourceType | None = None,
        page: int = 1, page_size: int | None = 20
    ) -> tuple[int, Sequence[Resource]]:
        """获取知识库资源列表（分页），page_size=None 时返回全部。
        未指定 resource_type 时，优先展示 model3d 类型的资源。
        """
        where = [
            Resource.space_id == space_id,
            Resource.kbase_id == kbase_id,
            Resource.status != ResourceStatus.destroyed,
            *([Resource.type == resource_type] if resource_type else [])
        ]
        count_query = select(func.count()).select_from(Resource).where(*where)
        total = (await self.session.execute(count_query)).scalar()

        # 未指定类型筛选时，model3d 优先排序（sort_priority=0），其余类型次之（sort_priority=1）
        sort_priority = case(
            (Resource.type == ResourceType.model3d, 0),
            else_=1,
        )
        query = (
            select(Resource)
            .where(*where)
            .order_by(sort_priority, Resource.created_at.desc())
        )
        if page_size is not None:
            query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return total, result.scalars().all()

    async def get_similar_resource_names(self, space_id: UUID, kbase_id: UUID, base_stem: str, suffix: str) -> set[str]:
        """查询知识库中与指定文件名同名或同前缀的未销毁资源名称集合。
        例如 base_stem='report', suffix='.pdf' 会匹配 'report.pdf'、'report(1).pdf' 等。
        """
        result = await self.session.execute(
            select(Resource.name).where(
                Resource.space_id == space_id,
                Resource.kbase_id == kbase_id,
                Resource.status != ResourceStatus.destroyed,
                Resource.name.like(f"{base_stem}%{suffix}"),
            )
        )
        return set(result.scalars().all())

    async def get_resource_by_id(self, space_id: UUID, kbase_id: UUID, resource_id: UUID) -> Resource | None:
        """根据ID获取知识库资源"""
        result = await self.session.execute(
            select(Resource).where(
                Resource.space_id == space_id,
                Resource.kbase_id == kbase_id,
                Resource.uuid == resource_id,
                Resource.status != ResourceStatus.destroyed
            )
        )
        return result.scalar_one_or_none()

    async def get_doc_resource(self, space_id: UUID, kbase_id: UUID, resource_id: UUID,
                               ignore_not_existed=False) -> Resource:
        """获取文档类型资源，不存在时抛出异常"""
        resource = await self.get_resource_by_id(space_id, kbase_id, resource_id)
        if not resource and not ignore_not_existed:
            logger.error(f"文件ID: {resource_id} 不存在，获取文件信息失败")
            raise DocNotExistedError(resource_id)
        return resource

    async def get_docs_by_kbase(self, space_id: UUID, kbase_id: UUID) -> Sequence[Resource]:
        """获取知识库下的所有文档类型资源"""
        result = await self.session.execute(
            select(Resource).where(
                Resource.space_id == space_id,
                Resource.kbase_id == kbase_id,
                Resource.type == ResourceType.doc,
                Resource.status == "active"
            )
        )
        return result.scalars().all()

    async def update_resource(self, resource: Resource) -> Resource:
        """更新资源"""
        self.session.add(resource)
        await self.session.flush()
        return resource

    async def update_resource_processed_info(self, space_id: UUID, kbase_id: UUID,
                                             resource_id: UUID, processed_oss_path: str,
                                             chunk_size: int, summary) -> Resource:
        """更新文档资源的解析完成信息"""
        resource = await self.get_doc_resource(space_id, kbase_id, resource_id)
        if not resource:
            logger.error(f"文件ID: {resource_id} 不存在，更新处理信息失败")
            raise DocNotExistedError(resource_id)
        resource.processed_oss_path = processed_oss_path
        resource.status = ResourceStatus.received
        resource.chunk_size = chunk_size
        resource.summary = summary
        self.session.add(resource)
        await self.session.flush()
        return resource


    async def get_chunks(self, space_id: UUID, kbase_id: UUID, doc_id: UUID, page: int = 1, page_size: int = 20) -> tuple[int, Sequence]:
        """获取文档分块列表（分页）"""
        where = [
            # Chunk.space_id == space_id,
            # Chunk.kbase_id == kbase_id,
            Chunk.doc_id == doc_id,
        ]
        count_query = select(func.count()).select_from(Chunk).where(*where)
        total = (await self.session.execute(count_query)).scalar()

        query = select(Chunk).where(*where).order_by(Chunk.index, Chunk.created_at).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return total, result.scalars().all()

    async def get_chunk_detail(self, space_id: UUID, kbase_id: UUID, doc_id: UUID, chunk_id: UUID) -> Chunk:
        """获取分块详情"""
        query = select(Chunk).where(
            # Chunk.space_id == space_id,
            # Chunk.kbase_id == kbase_id,
            Chunk.doc_id == doc_id,
            Chunk.uuid == chunk_id
        )
        result = await self.session.execute(query)
        chunk = result.scalar_one_or_none()
        if not chunk:
            logger.error(f"分块ID: {chunk_id} 不存在，获取分块详情失败")
            raise ChunkNotExistedError(chunk_id)
        return chunk

    async def delete_kbase_resources(self, space_id: UUID, kbase_id: UUID) -> None:
        """删除知识库下的所有资源（逻辑删除）"""
        _, resources = await self.get_resources(space_id, kbase_id, page_size=None)
        for resource in resources:
            resource.status = ResourceStatus.destroyed
            self.session.add(resource)
        await self.session.flush()

    async def delete_kbase_vector_data(self, space_id: UUID, kbase_id: UUID):
        """删除知识库下的所有向量数据"""
        kbase = await self.get_kbase_by_id(space_id, kbase_id)
        if not kbase:
            logger.error(f"知识库ID: {kbase_id} 不存在，删除向量数据失败")
            raise KBaseNotExistedError(kbase_id)
        res = await ParserClient().delete_collection(kbase.collection_name)
        return res

    async def get_default_questions(self, space_id: UUID, kbase_id: UUID) -> Sequence:
        """获取知识库默认问题列表"""
        result = await self.session.execute(
            select(DefaultQuestion).where(
                DefaultQuestion.space_id == space_id,
                DefaultQuestion.kbase_id == kbase_id,
            ).order_by(DefaultQuestion.order.asc(), DefaultQuestion.created_at.asc())
        )
        questions = result.scalars().all()
        return [
            {
                "uuid": r.uuid,
                "question": r.question,
                "order": r.order,
            } for r in questions
        ]

    async def insert_questions(self, space_id: UUID, kbase_id: UUID, question) -> DefaultQuestion:
        """插入默认问题"""
        orm_obj = DefaultQuestion(
            space_id=space_id,
            kbase_id=kbase_id,
            question=question.content,
            order=question.order,
        )
        self.session.add(orm_obj)
        await self.session.flush()
        return orm_obj

    async def delete_questions(self, space_id: UUID, kbase_id: UUID, question_id: UUID) -> None:
        await self.session.execute(
            delete(DefaultQuestion).where(
                DefaultQuestion.space_id == space_id,
                DefaultQuestion.kbase_id == kbase_id,
                DefaultQuestion.uuid == question_id,
            )
        )
        await self.session.flush()

    async def get_chat_resources(self, space_id: UUID, chat_resouce_ids: list) -> Sequence:
        """获取知识库绑定所有对话资源"""
        ids = [UUID(res_id) for res_id in chat_resouce_ids] if chat_resouce_ids else []
        result = await self.session.execute(
            select(ChatResource).where(
                ChatResource.space_id == space_id,
                ChatResource.uuid.in_(ids)
            )
        )
        return result.scalars().all()

    async def get_resource_by_collection(self, collection_name):
        """根据知识库集合名称获取资源"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.collection_name == collection_name,
                KnowledgeBase.status != ResourceStatus.destroyed
            )
        )
        kbase = result.scalar_one_or_none()
        if kbase:
            result = await self.session.execute(
                select(Resource).where(
                    Resource.space_id == kbase.space_id,
                    Resource.kbase_id == kbase.uuid,
                    Resource.status != ResourceStatus.destroyed
                )
            )
            resources = result.scalars().all()
        else:
            logger.error("内部查询知识库资源路径时报错，知识库不存在，请检查。")
            return []
        return resources