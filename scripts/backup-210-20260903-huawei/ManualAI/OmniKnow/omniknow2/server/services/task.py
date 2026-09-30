import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from services.document import DocumentService
from schemas import CurrentUser
from core.acl.schema import ResourceStatus
from utils import logger
from schemas.task import TaskResponse, TaskProgressResponse, TaskStatusQuerySchema
from exceptions.errors.task import TaskNotExisted


# 文档类型常量（与 backend/document_worker.py 保持一致）
DOC_TYPE_DOCUMENT = "document"
DOC_TYPE_VIDEO = "video"


class TaskService:
    def __init__(self, redis: Redis, session: AsyncSession):
        self.session = session
        self.redis = redis
        self.doc_service = DocumentService.internal(session, redis)
        # doc_type → finalizer 注册表，新增类型时只需在此追加
        self._finalizers = {
            DOC_TYPE_DOCUMENT: self.doc_service.finalize_parse_task,
            DOC_TYPE_VIDEO: self.doc_service.finalize_parse_video_task,
        }

    async def _get_task_or_raise(self, task_id: str) -> dict:
        """从 Redis 读取任务数据，不存在则抛出异常"""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            raise TaskNotExisted(task_id)
        return task_data

    async def _set_task_status(self, task_id: str, status: str, message: str) -> None:
        """更新 Redis 中的任务状态与消息"""
        await self.redis.hset(f"task:{task_id}", mapping={
            "status": status,
            "message": message,
        })

    async def _acquire_lock(self, task_id: str, ttl: int = 600) -> bool:
        """
        尝试获取 Redis 分布式锁。

        使用 SET NX（仅在 key 不存在时设置）实现互斥，
        TTL 防止进程崩溃后锁永远无法释放。
        """
        lock_key = f"lock:task_callback:{task_id}"
        acquired = await self.redis.set(lock_key, "1", nx=True, ex=ttl)
        return bool(acquired)

    async def _release_lock(self, task_id: str) -> None:
        """释放 Redis 分布式锁"""
        lock_key = f"lock:task_callback:{task_id}"
        await self.redis.delete(lock_key)

    async def task_complete_callback(self, task_id: str):
        """
        任务完成回调。

        操作顺序（保证一致性）：
          0. Redis 分布式锁 —— 防止并发重复处理
          1. 幂等检查 —— 若资源已「received」则直接返回
          2. 上传 OSS（幂等操作，失败不影响 DB，可重试）
          3. DB 事务：更新资源状态 + 写入分块（原子完成）
          4. 刷新 Redis 任务状态为 completed
          5. 清理本地临时文件（非关键，仅记录日志）

        任何步骤失败时，同步将 Redis 与 DB 状态标为 failed，
        并保留本地文件以支持重试。
        """
        # 0. 分布式锁
        if not await self._acquire_lock(task_id):
            logger.warning(f"任务 {task_id} 回调正在处理中，跳过重复请求")
            return True

        try:
            return await self._do_complete_callback(task_id)
        finally:
            await self._release_lock(task_id)

    async def _do_complete_callback(self, task_id: str):
        """完成回调的实际处理逻辑（已持有分布式锁）"""
        task_data = await self._get_task_or_raise(task_id)

        resource_id = UUID(task_data["file_id"])
        kbase_id = UUID(task_data["kbase_id"])
        space_id = UUID(task_data["space_id"])
        logger.info(f"任务 {task_id} | 开始处理回调，Space ID: {space_id}, 知识库 ID：{kbase_id}, 资源 ID: {resource_id}")

        # 1. 幂等检查（独立事务）
        async with self.session.begin():
            resource = await self.doc_service.kbase_repo.get_doc_resource(
                space_id, kbase_id, resource_id
            )
            if resource.status == ResourceStatus.received:
                logger.warning(f"任务 {task_id} 已处理，跳过重复回调")
                return True

        task = TaskResponse(**task_data)
        result = task.result or {}
        # 仅本地清理需要的通用字段；其余字段交给 finalizer 自行从 result 中解构
        source_file_path = result.get("source_file_path")
        processed_file_path = result.get("processed_file_path")
        doc_type = result.get("doc_type", DOC_TYPE_DOCUMENT)

        finalizer = self._finalizers.get(doc_type)
        if finalizer is None:
            logger.error(f"任务 {task_id} | 不支持的文档类型: {doc_type}")
            await self._set_task_status(
                task_id, ResourceStatus.failed, f"不支持的文档类型: {doc_type}"
            )
            async with self.session.begin():
                await self.doc_service.mark_resource_failed(
                    space_id, kbase_id, resource_id
                )
            return False

        try:
            # 2. 解析回调后处理：按 doc_type 分发到对应 finalizer
            #    finalizer 统一接受 (task, result)；具体字段由各 finalizer 自行解构
            async with self.session.begin():
                logger.info(
                    f"任务 {task_id} | 进入后处理流程, doc_type={doc_type}, "
                    f"finalizer={finalizer.__name__}"
                )
                await finalizer(task, result)
                logger.info(f"任务 {task_id} | 资源 {resource_id} 已解析完成")

            # 3. 刷新 Redis 状态
            await self._set_task_status(task_id, ResourceStatus.completed, "解析完成")

            # 4. 提取文档封面并上传OSS（非关键路径，失败不影响核心结果）
            # try:
            #     logger.info(f"任务 {task_id} | 开始提取文档封面")
            #     if source_file_path and source_file_path.endswith(".pdf"):
            #         url = await self.doc_service.extract_and_upload_cover(space_id, kbase_id, source_file_path)
            #     elif processed_file_path:
            #         url = await self.doc_service.extract_and_upload_cover(space_id, kbase_id, processed_file_path)
            #     else:
            #         logger.warning(f"任务 {task_id} | 无有效文件路径，跳过封面提取")
            #
            # except Exception as e:
            #     logger.warning(f"任务 {task_id} | 提取或上传封面失败（不影响核心结果）: {e}")

        except Exception as e:
            logger.error(f"任务 {task_id} 回调处理失败: {e}")
            try:
                await self._set_task_status(
                    task_id, ResourceStatus.failed, f"回调处理失败: {str(e)[:200]}"
                )
                async with self.session.begin():
                    await self.doc_service.mark_resource_failed(
                        space_id, kbase_id, resource_id
                    )
            except Exception as inner_e:
                logger.error(f"任务 {task_id} 失败状态回写出错: {inner_e}")
            raise

        # 4. 清理本地文件（非关键路径）
        try:
            await self.doc_service.storage.delete_local(source_file_path)
            await self.doc_service.storage.delete_local(processed_file_path)
            await self.redis.delete(f"file:{resource.md5}")
            logger.info(f"任务 {task_id} | 本地临时文件已清理")
        except Exception as e:
            logger.warning(f"任务 {task_id} 清理本地文件失败（不影响结果）: {e}")
        logger.info(f"任务 {task_id} | 文件 {task_data.get('file_name')} 处理完成")
        return True

    async def task_fail_callback(self, task_id: str, reason: str = ""):
        """
        任务失败回调（由 Worker 在执行失败时主动调用）。

        同步将 DB 资源状态更新为「failed」，并刷新 Redis 任务状态。
        幂等：若资源已为「failed」则直接返回。
        """
        task_data = await self._get_task_or_raise(task_id)

        resource_id = UUID(task_data["file_id"])
        kbase_id = UUID(task_data["kbase_id"])
        space_id = UUID(task_data["space_id"])
        message = reason or "Worker 执行失败"

        async with self.session.begin():
            resource = await self.doc_service.kbase_repo.get_doc_resource(
                space_id, kbase_id, resource_id
            )
            if resource is None:
                logger.warning(f"任务 {task_id} 对应资源不存在，跳过")
                return True
            if resource.status == ResourceStatus.failed:
                logger.warning(f"任务 {task_id} 已标记为失败，跳过重复回调")
                return True
            await self.doc_service.mark_resource_failed(space_id, kbase_id, resource_id)

        await self._set_task_status(task_id, "failed", message)
        logger.info(f"任务 {task_id} | 已标记为失败: {message}")
        return True

    async def get_task_progress(self, request: TaskStatusQuerySchema, user: CurrentUser) -> list[Any]:
        """获取任务进度"""
        task_ids = request.task_ids
        task_progress_list = []
        for task_id in task_ids:
            task_data = await self.redis.hgetall(f"task:{task_id}")
            if not task_data:
                raise TaskNotExisted(str(task_id))

            if str(user.uuid) != task_data.get("user_id"):
                raise HTTPException(status_code=403, detail="没有权限查看该任务进度")

            status = task_data.get("status")
            result_str = task_data.get("result", "")
            result = json.loads(result_str) if result_str else {}
            created_at = task_data.get("created_at")
            chunks = result.get("length", 0) if status == "completed" else 0
            task_progress_list.append(TaskProgressResponse(
                task_id=task_id,
                doc_id=task_data.get("file_id"),
                doc_name=task_data.get("file_name"),
                status=status,
                message=task_data.get("message"),
                metadata={"chunks": chunks, "date": created_at} if status == "completed" else None,
        ))
        return task_progress_list
