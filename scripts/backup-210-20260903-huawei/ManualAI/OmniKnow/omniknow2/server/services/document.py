"""
文档 / 资源业务服务层。

承接此前散落在 `core/resource_manager.py`（业务编排 + DTO 组装）与
`services/kbase.py`（部分资源级方法）中的逻辑。职责：
  - 批量上传（含文件名去重）
  - Markdown upsert 生命周期
  - 资源删除 / 归档的跨系统级联（ACL + Milvus + OSS + DB）
  - 解析任务分发 + 解析回调后处理（finalize_parse_task）
  - 列表 / 分块 / 详情等 DTO 组装与预签 URL 生成

所有资源访问都通过 `ResourceManager`（鉴权 + 原子 CRUD）；
所有文件存储交互通过 `StorageService`；所有向量库交互通过 `MilvusClient`。
"""

import re
from datetime import datetime
import traceback
import uuid
from pathlib import PurePosixPath
from uuid import UUID

from fastapi import UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from chunks.service import ChunkService
from core.config import settings
from core.dependencies import RequestContext
from core.acl.guard import ResourceGuard
from exceptions.errors.resource import (
    ChunkNotExistedError,
    DocNotExistedError,
    DocNotParsedError,
    FileUploadError,
    KBaseNotExistedError,
    ResourceNotExistedError, ResourceNotChunks,
)
from exceptions.errors.task import TaskSubmissionError
from parser import ParseTask, dispatch_parse_task
from storage import get_storage
from storage import paths as storage_paths
from repository import KBaseRepository, UserRepository
from repository.resource import ResRepository
from schemas import Action, DocParseRequest, TaskResponse
from schemas.kbase import MarkdownUploadSchema
from core.acl.schema import ResourceStatus, ResourceType
from utils import logger
from utils.public import check_file_source, count_chars, get_resource_type
from vector import ParserClient, MilvusClient


# ─── 文件名去重（原 resource_manager 模块级函数） ───────────────────

def _parse_filename(filename: str) -> tuple[str, str, str]:
    """解析文件名，返回 (base_stem, suffix, stem)。"""
    p = PurePosixPath(filename)
    stem, suffix = p.stem, p.suffix
    match = re.match(r"^(.+?)\((\d+)\)$", stem)
    base_stem = match.group(1) if match else stem
    return base_stem, suffix, stem


def _deduplicate_filename(filename: str, existing_names: set[str]) -> str:
    """文件名去重，重名时追加 (1)、(2) 等后缀。"""
    if filename not in existing_names:
        return filename
    base_stem, suffix, stem = _parse_filename(filename)
    match = re.match(r"^(.+?)\((\d+)\)$", stem)
    start = int(match.group(2)) + 1 if match else 1
    counter = start
    while True:
        candidate = f"{base_stem}({counter}){suffix}"
        if candidate not in existing_names:
            return candidate
        counter += 1


class DocumentService:
    """文档 / 资源业务流程服务。"""

    def __init__(self, ctx: RequestContext):
        self.session = ctx.db
        self.user = ctx.user
        self.rm = ResourceGuard(ctx)
        self.storage = get_storage()
        self.vector = ParserClient()
        self.chunk_serv = ChunkService(ctx.db)
        self.user_repo = UserRepository(ctx.db)
        self.kbase_repo = KBaseRepository(ctx.db)
        self.res_repo = ResRepository(ctx.db)

    @classmethod
    def internal(cls, session: AsyncSession, redis: Redis = None) -> "DocumentService":
        """供系统回调（task worker）使用，跳过鉴权。"""
        inst = cls.__new__(cls)
        inst.session = session
        inst.user = None
        inst.rm = ResourceGuard.internal(session, redis)
        inst.storage = get_storage()
        inst.vector = ParserClient()
        inst.chunk_serv = ChunkService(session)
        inst.user_repo = UserRepository(session)
        inst.kbase_repo = KBaseRepository(session)
        inst.res_repo = ResRepository(session)
        return inst

    # ─── 资源列表 / 详情 ─────────────────────────────────────────────

    async def get_kbase_resource_list(
        self,
        space_id: UUID,
        kbase_id: UUID,
        resource_type: ResourceType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取知识库资源列表"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        total, resources = await self.kbase_repo.get_resources(
            space_id, kbase_id, resource_type, page, page_size
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "uuid": res.uuid,
                    "name": res.name,
                    "type": res.type,
                    "size": res.size,
                    "doc_type": res.file_type,
                    "link": res.link,
                    "summary": res.summary,
                    "tag": res.tag,
                    "owner": res.owner_id,
                    "status": res.status,
                    "description": res.description,
                    "created_at": res.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": res.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for res in resources
            ],
        }

    async def get_kbase_file_list(self, space_id: UUID, kbase_id: UUID) -> list[dict]:
        """获取知识库文档列表（type=doc）"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        docs = await self.kbase_repo.get_docs_by_kbase(space_id, kbase_id)
        return [
            {
                "uuid": doc.uuid,
                "name": doc.name,
                "description": doc.description,
                "logo": doc.logo,
                "size": doc.size,
                "type": doc.file_type,
                "md5": doc.md5,
                "status": doc.status,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            }
            for doc in docs
        ]

    async def get_resource_detail(
        self, space_id: UUID, kbase_id: UUID, resource_id: UUID
    ) -> dict:
        """获取单个资源详情（含 owner 与预签 URL）。"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        resource = await self.kbase_repo.get_resource_by_id(space_id, kbase_id, resource_id)
        if not resource:
            raise ResourceNotExistedError

        user = await self.user_repo.get_by_id(resource.owner_id)
        data = resource.as_dict()
        data["owner_name"] = user.name if user else "未知用户"
        data["path"] = await self._presign_source(space_id, resource)
        data["processed_oss_key"] = data.get("processed_oss_path")
        data["processed_oss_path"] = await self._presign_processed(space_id, resource)
        return data

    async def _presign_source(self, space_id: UUID, resource) -> str | None:
        if not resource.path:
            return None
        return await self.storage.presign(space_id, resource.path)

    async def _presign_processed(self, space_id: UUID, resource) -> str | None:
        if not resource.processed_oss_path or resource.processed_oss_path == "1":
            return None
        return await self.storage.presign(space_id, resource.processed_oss_path)

    # ─── 下载 ────────────────────────────────────────────────────────

    async def download_resource(
        self, space_id: UUID, kbase_id: UUID, resource_id: UUID
    ) -> dict:
        """下载资源：返回 source/processed 两个预签名 URL。"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)

        resource = await self.kbase_repo.get_resource_by_id(space_id, kbase_id, resource_id)
        if not resource:
            raise ResourceNotExistedError(f"资源 {resource_id} 不存在")
        # if resource.type != ResourceType.doc or resource.type != ResourceType.video:
        #     raise ResourceNotExistedError(f"资源 {resource_id} 不是文档类型，无法下载")
        if not resource.path:
            raise ResourceNotExistedError(f"文档 {resource_id} 无源文件路径")

        source_url = await self.storage.presign(space_id, resource.path)
        processed_url = await self._presign_processed(space_id, resource)
        return {"source": source_url, "processed": processed_url}

    # ─── 批量上传（含去重） ──────────────────────────────────────────

    async def upload_file_group_to_kbase(
        self, space_id: UUID, kbase_id: UUID, files: list[UploadFile]
    ) -> dict:
        """批量上传文件到知识库（自动鉴权，同名文件自动重命名）"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_upload)

        kbase = await self.kbase_repo.get(space_id, kbase_id)
        if not kbase:
            raise KBaseNotExistedError(kbase_id)
        kbase_name = kbase.name

        # 批次内已使用的名称缓存，按 (base_stem, suffix) 分组，防止同批次内重名
        batch_used_names: dict[tuple[str, str], set[str]] = {}
        results = []
        has_duplicates = False
        await self.session.rollback()

        for file in files:
            async with self.session.begin():
                base_stem, suffix, _ = _parse_filename(file.filename)
                cache_key = (base_stem, suffix)
                if cache_key not in batch_used_names:
                    db_names = await self.kbase_repo.get_similar_resource_names(
                        space_id, kbase_id, base_stem, suffix
                    )
                    batch_used_names[cache_key] = db_names

                resolved_name = _deduplicate_filename(file.filename, batch_used_names[cache_key])
                if resolved_name != file.filename:
                    has_duplicates = True
                batch_used_names[cache_key].add(resolved_name)

                rename_info = (
                    f" -> 重命名为 {resolved_name}"
                    if resolved_name != file.filename
                    else ""
                )
                logger.info(
                    f"用户 {self.user.uuid} 在空间 {space_id} 的知识库 {kbase_id} "
                    f"上传文件 {file.filename}{rename_info}"
                )
                result = await self._upload_single_file(
                    space_id, kbase_id, kbase_name, file, resolved_name
                )
                results.append(result)

        return {"files": results, "has_duplicates": has_duplicates}

    async def _upload_single_file(
        self,
        space_id: UUID,
        kbase_id: UUID,
        kbase_name: str,
        file: UploadFile,
        resolved_name: str | None = None,
    ) -> dict:
        """单文件上传：存储落盘 + 资源记录写入（事务由调用方管理）。"""
        actual_name = resolved_name or file.filename
        file_ext = actual_name.rsplit(".", 1)[-1].lower() if "." in actual_name else ""
        if resolved_name and resolved_name != file.filename:
            file.filename = resolved_name
        saved = await self.storage.save_source(file, space_id, kbase_name)
        oss_path = saved.key
        md5 = saved.md5

        resource_type = await get_resource_type(file_ext)

        resource = await self.kbase_repo.add_resource(
            space_id=space_id,
            kbase_id=kbase_id,
            name=actual_name,
            resource_type=resource_type,
            owner=self.user.uuid if self.user else None,
            path=oss_path,
            size=file.size,
            md5=md5,
            content="",
            file_type=file_ext,
            chunk_size=0,
            status=ResourceStatus.pending,
            source="upload",
        )
        is_renamed = resolved_name is not None and resolved_name != file.filename
        return {
            "uuid": resource.uuid,
            "name": resource.name,
            "size": resource.size,
            "type": resource.file_type,
            "status": resource.status,
            "md5": resource.md5,
            "renamed": is_renamed,
            "original_name": file.filename if is_renamed else None,
        }

    # ─── Markdown ────────────────────────────────────────────────────

    async def upsert_markdown_doc(
        self, space_id: UUID, kbase_id: UUID, md: MarkdownUploadSchema
    ) -> dict:
        """新增或更新 Markdown 文档。"""
        if not md.content or not md.content.strip():
            raise FileUploadError("Markdown 内容不能为空")

        file_name = md.name if md.name.endswith(".md") else f"{md.name}.md"
        content_bytes = md.content.encode("utf-8")
        file_size = len(content_bytes)

        # 事务1：ACL 检查 + 创建/重置资源记录
        async with self.session.begin():
            await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_edit)
            kbase = await self.kbase_repo.get(space_id, kbase_id)
            oss_path = storage_paths.source_key(space_id, kbase.name, file_name)
            # DB 里存 bucket 相对路径（不含 space_id 前缀），与原语义一致
            oss_path = oss_path[len(f"{space_id}/"):]

            if md.uuid:
                resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, md.uuid)
                resource.status = ResourceStatus.pending
                resource.chunk_size = 0
                resource.processed_oss_path = None
                resource.name = file_name
                resource.content = md.content
                await self.kbase_repo.update_resource(resource)
            else:
                resource = await self.kbase_repo.add_resource(
                    space_id=space_id,
                    kbase_id=kbase_id,
                    name=file_name,
                    resource_type=ResourceType.doc,
                    owner=self.user.uuid,
                    path=oss_path,
                    size=file_size,
                    md5="",
                    content=md.content,
                    file_type="md",
                    chunk_size=0,
                    status="pending",
                    source="edit",
                )

        # 事务外：上传至本地 + 持久存储 + 计算 MD5 + Redis 缓存
        logger.info(
            "正在上传 Markdown 文件至存储",
            extra={"space_id": space_id, "kbase_id": kbase_id, "name": file_name},
        )
        try:
            saved = await self.storage.save_source_bytes(
                content_bytes=content_bytes,
                space_id=space_id,
                kbase_name=kbase.name,
                file_name=file_name,
                content_type="text/markdown",
            )
            md5 = saved.md5
        except Exception as e:
            logger.exception(
                f"Markdown 上传失败: space_id={space_id}, kbase_id={kbase_id}, file_name={file_name}"
            )
            raise FileUploadError(f"Markdown 上传失败: {e}")

        # 事务2：回填 OSS 路径 + MD5
        async with self.session.begin():
            resource.name = file_name
            resource.path = oss_path
            resource.md5 = md5
            resource.size = file_size
            resource.file_type = "md"
            await self.kbase_repo.update_resource(resource)

        return {
            "uuid": resource.uuid,
            "name": resource.name,
            "size": resource.size,
            "type": resource.file_type,
            "status": resource.status,
        }

    async def get_markdown_doc(
        self, space_id: UUID, kbase_id: UUID, doc_id: UUID
    ) -> dict:
        """获取 Markdown 文档内容。"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, doc_id)
        if not resource:
            raise ResourceNotExistedError(f"Markdown 文档 {doc_id} 不存在")
        if resource.file_type != "md":
            raise ResourceNotExistedError(f"文件 {doc_id} 不是 Markdown 文档")

        return {
            "doc_id": resource.uuid,
            "name": resource.name,
            "content": resource.content,
            "size": resource.size,
            "status": resource.status,
        }

    # ─── 删除 / 归档（跨系统级联） ───────────────────────────────────

    async def delete_resource(
        self, space_id: UUID, kbase_id: UUID, resource_id: UUID
    ) -> bool:
        """删除资源：ACL + 向量库 + OSS + DB 级联清理。"""
        async with self.session.begin():
            await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_delete)

            kbase = await self.kbase_repo.get_kbase_by_id(space_id, kbase_id)
            if not kbase:
                raise KBaseNotExistedError(kbase_id)

            resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, resource_id)

            # 1. ACL
            await self.rm.acl.delete_acl(
                space_id=space_id, resource_type="document", resource_id=resource_id
            )
            # 2. 向量库
            await self.vector.delete_resource_data(kbase.collection_name, resource.uuid)
            # 3. 对象存储
            await self.storage.delete_resource_files(
                space_id, resource.path, resource.processed_oss_path
            )
            # 4. DB 软删
            await self.res_repo.delete_resource(space_id, kbase_id, resource_id)

        return True

    async def archive_resource(
        self, space_id: UUID, kbase_id: UUID, resource_id: UUID
    ) -> bool:
        """归档资源：清向量库 + 状态改为 archived。"""
        async with self.session.begin():
            await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_delete)
            kbase = await self.kbase_repo.get_kbase_by_id(space_id, kbase_id)
            if not kbase:
                raise KBaseNotExistedError(kbase_id)

            resource = await self.kbase_repo.get_resource_by_id(space_id, kbase_id, resource_id)
            await self.vector.delete_resource_data(kbase.collection_name, resource.uuid)
            await self.res_repo.archive_resource(
                space_id=space_id, kbase_id=kbase_id, resource_id=resource_id
            )
        return True

    # ─── 解析分发 ────────────────────────────────────────────────────

    async def   parse_documents(
        self, space_id: UUID, kbase_id: UUID, request: DocParseRequest
    ) -> list[dict]:
        """对已上传的文档发起解析。"""
        task_ids = []
        opts = request.parse_config

        async with self.session.begin():
            await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_parse)
            kbase = await self.kbase_repo.get(space_id, kbase_id)

        for doc_id in request.doc_ids:
            async with self.session.begin():
                resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, doc_id)
                if not resource:
                    raise FileUploadError(f"文件 {doc_id} 不存在")
                if resource.status == ResourceStatus.received:
                    logger.info(f"文档：{resource.uuid} 已完成解析，执行覆盖")
                resource.status = ResourceStatus.parsing
                await self.kbase_repo.update_resource(resource)

            file_path, key = await self.storage.get_or_fetch_source(
                resource.md5, resource.path, space_id, kbase.name, resource.name
            )
            chunk_source = await check_file_source(resource.name)

            task = ParseTask(
                user_id=str(self.user.uuid),
                file_id=str(resource.uuid),
                file_name=resource.name,
                md5=resource.md5,
                file_path=file_path,
                source_oss_path=key,
                space_id=str(space_id),
                kbase_id=str(kbase_id),
                kbase_name=kbase.name,
                collection_name=kbase.collection_name,
                chunk_source=chunk_source,
                parse_config=opts,
            )

            try:
                task_id = await dispatch_parse_task(task)
                logger.info(f"已投递任务 {task_id} 到队列, 参数如下:\n{opts}")
            except TypeError:
                traceback.print_exc()
                logger.error(f"任务 {task.task_id} 调度失败，参数解析错误: {opts}")
                raise TaskSubmissionError("参数解析错误")
            task_ids.append({"task_id": task_id, "doc_id": doc_id})

        return task_ids

    # ─── 解析回调后处理 ───────────────────────────

    async def finalize_parse_task(self, task, result: dict) -> None:
        """普通文档任务的回调后处理流程。

        从 result 中读取的字段：
          - chunks (list)
          - summary (str)
          - processed_file_path (str | None)

        步骤：
          1. 上传处理后文件到 OSS
          2. 遍历 chunks，上传媒体到 OSS，组装 chunk payload
          3. 写入向量库 (Milvus document_insert)
          4. 更新资源解析完成信息
          5. 清空旧分块 + 写入新分块
        事务由调用方（TaskService）控制。
        """
        chunks: list = result.get("chunks", [])
        summary: str = result.get("summary", "")
        processed_local = result.get("processed_file_path")

        space_id = UUID(task.space_id)
        kbase_id = UUID(task.kbase_id)
        resource_id = UUID(task.file_id)

        # 1. 处理后文件上传
        upload_result = await self.storage.save_processed(
            processed_local, space_id, task.kbase_name
        ) if processed_local else True
        if upload_result is True:
            oss_path = True
        elif upload_result is False:
            oss_path = False
        else:
            # 把 key（含 space_id 前缀）还原成 `{bucket}/{object}` 形态，保持原返回语义
            oss_path = upload_result

        # 2. 遍历 chunks + 媒体上传
        media_chunks = [
            c
            for c in chunks
            if c.get("media_path") and self.storage.local_exists(c["media_path"])
        ]
        skipped = len(chunks) - len(media_chunks)
        if skipped:
            logger.warning(f"跳过 {skipped} 个无媒体文件或文件不存在的分块")

        resource = await self.kbase_repo.get_resource_by_id(space_id, kbase_id, resource_id)
        resource_source_path = resource.path if resource else "未知路径"

        for chunk in chunks:
            # 源文件直链 URL
            chunk["file_path"] = await self.storage.public_url(task.space_id, resource_source_path)
            media_path = chunk.get("media_path")
            if not media_path:
                continue
            chunk.setdefault("others", {})
            chunk["others"]["source_media_path"] = media_path
            chunk["others"]["img_id"] = str(uuid.uuid4())
            chunk["media_path"] = await self.storage.save_media(
                task.space_id, task.kbase_name, media_path
            )

        # 3. 向量库写入
        await self.vector.document_insert(
            chunks=chunks,
            doc_summary=summary,
            collection_name=task.collection_name,
        )
        logger.info("文件上传 OSS 并插入 Milvus 完成")

        # 4. 更新资源解析完成信息
        chunk_count = len(chunks)
        await self.kbase_repo.update_resource_processed_info(
            space_id, kbase_id, resource_id, oss_path, chunk_count, summary
        )

        # 5. 清空旧分块 + 写入新分块
        await self.chunk_serv.clear_chunks(space_id, kbase_id, resource_id)
        await self.chunk_serv.insert_chunks(space_id, kbase_id, resource_id, chunks)

    async def finalize_parse_video_task(self, task: TaskResponse, result: dict):
        """视频任务的回调后处理。

        result 字段契约（由 backend.document_worker.VideoHandler 写入）：
          - embeddings (dict):   视频解析接口的原始响应（含切片 / 摘要 / 元信息等）
          - source_file_path:    源视频本地路径

        与文档流程的差异：
          - 视频不做格式转换，无 processed_file_path，跳过 OSS 处理后文件上传
          - 资源 oss_path 置为 True（无 processed 副本）
          - 入参形状由 video parser 决定，本方法负责消费 `embeddings`
        事务由调用方（TaskService）控制。

        具体逻辑。当前仅完成资源状态推进与日志记录，避免阻塞主流程。
        """
        embeddings: list = result.get("embeddings") or {}

        space_id = UUID(task.space_id)
        kbase_id = UUID(task.kbase_id)
        resource_id = UUID(task.file_id)
        collection_name = task.collection_name

        logger.info(
            f"视频任务后处理 | embeddings_keys={len(embeddings)}, "
        )

        file_path = await self.storage.public_url("", task.source_oss_path)
        data = [{
            "chunk_id": str(resource_id),
            "chunk_index": 0,
            "content": task.file_name,
            "file_id": str(resource_id),
            "file_path": file_path,
            "bbox_type": "video",
            "title": task.file_name,
            "cur_title": task.file_name,
            "par_title": task.file_name,
            "embedding_summary": embeddings,
            "embedding_text": embeddings,
            "embedding_title": embeddings,
            "update_time": str(datetime.now()),
            "summary": task.file_name,
            "media_path": file_path,
            "chunk_source": "",
            "bbox": [],
            "page_idx": [],
            "others": {}
        }]
        milvus_client = MilvusClient()
        res = await milvus_client.insert(collection_name, data)

        # 资源信息更新（无 processed 副本，oss_path 置 True）
        await self.kbase_repo.update_resource_processed_info(
            space_id, kbase_id, resource_id, result.get("source_oss_path"), 0, ""
        )
        return res


    async def mark_resource_failed(
        self, space_id: UUID, kbase_id: UUID, resource_id: UUID
    ) -> None:
        """标记资源为解析失败（供 task.py 失败分支调用）。"""
        resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, resource_id)
        if resource is None:
            return
        resource.status = ResourceStatus.failed
        await self.kbase_repo.update_resource(resource)

    # ─── Chunk 列表 / 详情 ───────────────────────────────────────────

    async def get_doc_chunks(
        self,
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取文档分块列表"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)

        resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, doc_id)
        if not resource:
            raise ResourceNotExistedError
        if resource.chunk_size == 0:
            raise ResourceNotChunks

        total, chunks = await self.kbase_repo.get_chunks(
            space_id, kbase_id, doc_id, page=page, page_size=page_size
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "uuid": chunk.uuid,
                    "chunk_id": chunk.chunk_id,
                    "summary": chunk.summary,
                    "bbox_type": chunk.bbox_type,
                    "bbox": chunk.bbox,
                    "chunk_index": chunk.index,
                    "title": chunk.title,
                    "others": chunk.others,
                    "page_idx": chunk.page_idx,
                    "preview": chunk.content[:50],
                    "count": count_chars(chunk.content),
                    "created_at": chunk.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for chunk in chunks
            ],
        }

    async def get_doc_chunk_detail(
        self,
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        chunk_id: UUID,
    ) -> dict:
        """获取文档分块详情"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)

        resource = await self.kbase_repo.get_doc_resource(space_id, kbase_id, doc_id)
        if not resource:
            raise DocNotExistedError(doc_id)
        if resource.chunk_size == 0:
            raise DocNotParsedError(doc_id)

        chunk = await self.kbase_repo.get_chunk_detail(space_id, kbase_id, doc_id, chunk_id)
        if not chunk:
            raise ChunkNotExistedError(chunk_id)

        if chunk.media_path and chunk.media_path.startswith(str(space_id)):
            object_path = chunk.media_path.split("/", maxsplit=1)[-1]
            chunk.media_path = await self.storage.presign(space_id, object_path)

        return {
            "uuid": chunk.uuid,
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "summary": chunk.summary,
            "others": chunk.others,
            "title": chunk.title,
            "chunk_index": chunk.index,
            "page_idx": chunk.page_idx,
            "bbox_type": chunk.bbox_type,
            "bbox": chunk.bbox,
            "media_path": chunk.media_path,
            "created_at": chunk.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": chunk.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def get_doc_chunk_detail_by_index(
        self,
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        chunk_index: int,
    ):
        """通过分块索引获取文档分块详情"""
        await self.rm.check_kbase_access(space_id, kbase_id, Action.kbase_view)
        return await self.chunk_serv.get_chunk_detail_by_index(
            space_id, kbase_id, doc_id, chunk_index
        )

    async def get_resource_url_by_collection(self, collection_name: str):
        """根据 collection_name 获取资源 URL（供向量解析使用）"""
        resources = await self.kbase_repo.get_resource_by_collection(collection_name)
        if not resources:
            return []
        res_url_list = []
        for resource in resources:
            if resource.path:
                url = await self.storage.public_url(resource.space_id, resource.path)
            else:
                continue
            res_url_list.append({
                "name": resource.name,
                "url": url
            })
        return res_url_list

    async def extract_and_upload_cover(self, space_id: UUID, kbase_id: UUID, pdf_path: str):
        from utils.public import get_pdf_cover
        # 判断文件是否存在且为 PDF
        if not self.storage.local_exists(pdf_path):
            logger.warning(f"PDF 文件 {pdf_path} 不存在，无法提取封面")
            return None
        if not pdf_path.lower().endswith(".pdf"):
            logger.warning(f"文件 {pdf_path} 不是 PDF 格式，无法提取封面")
            return None

        # 提取封面并上传OSS
        try:
            cover_bytes = await get_pdf_cover(pdf_path)
            if not cover_bytes:
                logger.warning(f"PDF 文件 {pdf_path} 无法提取封面")
                return None
            cover_name = f"public/{kbase_id}/cover.jpg"
            await self.storage.put_bytes(space_id, cover_name, cover_bytes, content_type="image/png")
            cover_url = await self.storage.public_url(space_id, cover_name)
            return cover_url
        except Exception as e:
            logger.error(f"提取 PDF 文件 {pdf_path} 封面失败: {e}")
            return None
